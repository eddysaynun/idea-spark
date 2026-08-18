from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services.payment_reconciliation import query_and_fulfill, reconcile_payments, refund_prepared
from services.payments import PaymentQuery, PaymentRefund, PaymentRegistry


@pytest.mark.asyncio
async def test_query_and_refund_share_strict_provider_validation():
    order = {
        "id": "order-1", "channel": "alipay", "provider_order_id": "ISorder",
        "provider_trade_id": "trade-1", "amount_fen": 2900, "refund_request_id": "RForder",
        "status": "pending", "expires_at": "2000-01-01T00:00:00Z", "refund_state": "none",
    }
    store = SimpleNamespace(
        admin_payment_order=AsyncMock(return_value=order),
        fulfill_payment=AsyncMock(return_value={"status": "fulfilled", "order": order}),
        expire_payment_order=AsyncMock(return_value={**order, "status": "expired"}),
        complete_payment_refund=AsyncMock(return_value={"status": "refunded", "order": order}),
    )
    provider = SimpleNamespace(
        query_order=AsyncMock(return_value=PaymentQuery("ISorder", "trade-1", "paid", 2900)),
        refund_order=AsyncMock(return_value=PaymentRefund("ISorder", "trade-1", "RForder", 2900)),
    )
    registry = PaymentRegistry({"alipay": provider})

    assert (await query_and_fulfill("order-1", store, registry))["status"] == "fulfilled"
    assert (await refund_prepared(order, store, registry))["status"] == "refunded"

    provider.query_order.return_value = PaymentQuery("ISorder", "trade-1", "paid", 1)
    with pytest.raises(ValueError, match="mismatch"):
        await query_and_fulfill("order-1", store, registry)


@pytest.mark.asyncio
async def test_reconcile_payments_continues_after_one_provider_failure():
    pending = {"id": "pending", "channel": "alipay", "refund_state": "none"}
    refund = {
        "id": "refund", "channel": "alipay", "refund_state": "pending",
        "provider_order_id": "ISrefund", "refund_request_id": "RFrefund", "amount_fen": 2900,
    }
    store = SimpleNamespace(
        payment_reconciliation_candidates=AsyncMock(return_value=[pending, refund]),
        admin_payment_order=AsyncMock(side_effect=RuntimeError("temporary query failure")),
        complete_payment_refund=AsyncMock(return_value={"status": "refunded", "order": refund}),
    )
    provider = SimpleNamespace(refund_order=AsyncMock(return_value=PaymentRefund(
        "ISrefund", "trade-2", "RFrefund", 2900,
    )))

    result = await reconcile_payments(store, PaymentRegistry({"alipay": provider}), limit=20)

    assert result == {"processed": 1, "failed": 1}
    store.complete_payment_refund.assert_awaited_once()
