from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from routers.billing_router import PaymentOrderRequest, create_order, packages, payment_scene
from services.payments import AlipayProvider, PaymentRegistry


@pytest.mark.asyncio
async def test_packages_expose_fail_closed_channel_status():
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(payment_registry=PaymentRegistry())))
    result = await packages(request, {"id": "user"})

    assert result["payment_mode"] == "manual_review"
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


def test_payment_scene_selects_mobile_and_desktop_website_products():
    assert payment_scene("Mozilla/5.0 (iPhone; Mobile)") == "mobile"
    assert payment_scene("Mozilla/5.0 (Linux; Android 16)") == "mobile"
    assert payment_scene("Mozilla/5.0 (Macintosh; Intel Mac OS X)") == "desktop"
