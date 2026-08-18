from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from routers.billing_router import PaymentOrderRequest, create_order, packages, payment_scene
import routers.admin_router as admin_router_module
from services.payments import AlipayProvider, PaymentQuery, PaymentRefund, PaymentRegistry


@pytest.mark.asyncio
async def test_packages_expose_fail_closed_channel_status():
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(payment_registry=PaymentRegistry())))
    result = await packages(request, {"id": "user"})

    assert result["payment_mode"] == "unavailable"
    assert list(result["channels"]) == ["alipay"]
    assert result["channels"]["alipay"]["configured"] is False
    assert "应用 AppID" in result["channels"]["alipay"]["missing"]


@pytest.mark.asyncio
async def test_unconfigured_channel_cannot_create_fake_checkout():
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(payment_registry=PaymentRegistry())))
    with pytest.raises(HTTPException) as error:
        await create_order(PaymentOrderRequest(package_id="starter", channel="alipay"), request, {"id": "user"})
    assert error.value.status_code == 503
    assert "暂未开放" in error.value.detail


class FakeResponse:
    status = 200

    def __init__(self, value):
        self.value = value

    async def text(self):
        return __import__("json").dumps(self.value)


class FakeBinding:
    def __init__(self, value):
        self.value = value
        self.calls = []

    async def fetch(self, url, **options):
        self.calls.append((url, options))
        return FakeResponse(self.value)


@pytest.mark.asyncio
async def test_alipay_provider_uses_private_gateway_binding():
    binding = FakeBinding({"provider_order_id": "ISorder", "pay_url": "https://openapi.alipay.com/order"})
    provider = AlipayProvider(binding, "internal-token")

    checkout = await provider.create_checkout({
        "id": "order-id", "amount_fen": 2900, "package_name": "Starter",
    }, "https://idea.example", "mobile")

    assert checkout == {"provider_order_id": "ISorder", "pay_url": "https://openapi.alipay.com/order"}
    assert binding.calls[0][0] == "https://idea-spark-payment.internal/checkout"
    assert binding.calls[0][1]["headers"]["Authorization"] == "Bearer internal-token"
    payload = __import__("json").loads(binding.calls[0][1]["body"])
    assert payload["scene"] == "mobile"
    assert payload["return_url"] == "https://idea.example/account?payment=return&order_id=order-id"


@pytest.mark.asyncio
async def test_alipay_provider_queries_and_refunds_with_stable_internal_contract():
    binding = FakeBinding({
        "provider_order_id": "ISorder", "provider_trade_id": "trade-1", "status": "paid", "amount_fen": 2900,
    })
    provider = AlipayProvider(binding, "internal-token")
    order = {"provider_order_id": "ISorder", "amount_fen": 2900}

    queried = await provider.query_order(order)
    assert queried.status == "paid"
    assert queried.amount_fen == 2900
    assert binding.calls[-1][0].endswith("/query")

    binding.value = {
        "provider_order_id": "ISorder", "provider_trade_id": "trade-1",
        "refund_request_id": "RForder", "amount_fen": 2900,
    }
    refunded = await provider.refund_order(order, "RForder")
    assert refunded.refund_request_id == "RForder"
    assert binding.calls[-1][0].endswith("/refund")


def test_payment_scene_selects_mobile_and_desktop_website_products():
    assert payment_scene("Mozilla/5.0 (iPhone; Mobile)") == "mobile"
    assert payment_scene("Mozilla/5.0 (Linux; Android 16)") == "mobile"
    assert payment_scene("Mozilla/5.0 (Macintosh; Intel Mac OS X)") == "desktop"


@pytest.mark.asyncio
async def test_admin_query_fulfills_only_matching_paid_trade():
    order = {"id": "order-1", "channel": "alipay", "provider_order_id": "ISorder", "amount_fen": 2900}
    store = SimpleNamespace(
        admin_payment_order=AsyncMock(return_value=order),
        fulfill_payment=AsyncMock(return_value={"status": "fulfilled", "order": order}),
    )
    provider = SimpleNamespace(query_order=AsyncMock(return_value=PaymentQuery(
        provider_order_id="ISorder", provider_trade_id="trade-1", status="paid", amount_fen=2900,
    )))
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        account_store=store, payment_registry=PaymentRegistry({"alipay": provider}),
    )))

    result = await admin_router_module.query_payment_order("order-1", request)

    assert result["status"] == "fulfilled"
    store.fulfill_payment.assert_awaited_once()

    provider.query_order.return_value = PaymentQuery("ISorder", "trade-1", "paid", 1)
    with pytest.raises(HTTPException, match="mismatch"):
        await admin_router_module.query_payment_order("order-1", request)


@pytest.mark.asyncio
async def test_admin_refund_uses_prepared_stable_request_id():
    order = {
        "id": "order-1", "channel": "alipay", "provider_order_id": "ISorder",
        "amount_fen": 2900, "refund_request_id": "RForder",
    }
    store = SimpleNamespace(
        prepare_payment_refund=AsyncMock(return_value=order),
        complete_payment_refund=AsyncMock(return_value={"status": "refunded", "order": order}),
    )
    provider = SimpleNamespace(refund_order=AsyncMock(return_value=PaymentRefund(
        "ISorder", "trade-1", "RForder", 2900,
    )))
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        account_store=store, payment_registry=PaymentRegistry({"alipay": provider}),
    )))

    result = await admin_router_module.refund_payment_order("order-1", request)

    assert result["status"] == "refunded"
    provider.refund_order.assert_awaited_once_with(order, "RForder")
    store.complete_payment_refund.assert_awaited_once_with("order-1", "RForder", "trade-1")


@pytest.mark.asyncio
async def test_admin_payment_provider_failure_is_reported_as_bad_gateway():
    order = {"id": "order-1", "channel": "alipay", "provider_order_id": "ISorder", "amount_fen": 2900}
    store = SimpleNamespace(admin_payment_order=AsyncMock(return_value=order))
    provider = SimpleNamespace(query_order=AsyncMock(side_effect=RuntimeError("gateway unavailable")))
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        account_store=store, payment_registry=PaymentRegistry({"alipay": provider}),
    )))

    with pytest.raises(HTTPException) as error:
        await admin_router_module.query_payment_order("order-1", request)

    assert error.value.status_code == 502
