"""Shared, bounded payment reconciliation used by admin routes and cron."""

import hashlib
import logging

logger = logging.getLogger(__name__)


def _provider(order, registry):
    provider = registry.get(order["channel"])
    if provider is None:
        raise ValueError("Payment provider is not configured")
    return provider


async def query_and_fulfill(order_id, store, registry):
    order = await store.admin_payment_order(order_id)
    result = await _provider(order, registry).query_order(order)
    if result.provider_order_id != order["provider_order_id"] or result.amount_fen != int(order["amount_fen"]):
        raise ValueError("Payment query mismatch")
    if result.status != "paid":
        if result.status in {"pending", "closed"} and order["status"] == "pending":
            order = await store.expire_payment_order(order_id)
        return {"success": True, "status": result.status, "order": order}
    digest = hashlib.sha256(
        f"{result.provider_order_id}:{result.provider_trade_id}:{result.amount_fen}".encode()
    ).hexdigest()
    return {
        "success": True,
        **await store.fulfill_payment(
            order_id, order["channel"], f"query:{result.provider_trade_id}:paid", "TRADE_QUERY",
            result.provider_trade_id, result.amount_fen, digest, True,
        ),
    }


async def refund_prepared(order, store, registry):
    if order.get("status") == "refunded":
        return {"success": True, "status": "duplicate", "order": order}
    result = await _provider(order, registry).refund_order(order, order["refund_request_id"])
    if (
        result.provider_order_id != order["provider_order_id"]
        or result.refund_request_id != order["refund_request_id"]
        or result.amount_fen != int(order["amount_fen"])
    ):
        raise ValueError("Payment refund mismatch")
    return {
        "success": True,
        **await store.complete_payment_refund(
            order["id"], result.refund_request_id, result.provider_trade_id
        ),
    }


async def reconcile_payments(store, registry, limit=20):
    processed = failed = 0
    for order in await store.payment_reconciliation_candidates(limit):
        try:
            if order.get("refund_state") == "pending":
                await refund_prepared(order, store, registry)
            else:
                await query_and_fulfill(order["id"], store, registry)
            processed += 1
        except Exception as exc:
            failed += 1
            logger.error("Payment reconciliation failed for %s: %s", order["id"], exc)
    return {"processed": processed, "failed": failed}
