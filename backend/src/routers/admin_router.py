"""Audited commercial-account administration endpoints."""

import hashlib
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from routers.config_router import require_config_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_config_admin)])


class QuotaAdjustment(BaseModel):
    resource: Literal["idea", "detail"]
    delta: int = Field(..., ge=-1_000_000, le=1_000_000)
    reason: str = Field(..., min_length=3, max_length=300)


class ReservationRepair(BaseModel):
    resource: Literal["idea", "detail"]
    reason: str = Field(..., min_length=3, max_length=300)


def store(request: Request):
    value = getattr(request.app.state, "account_store", None)
    if value is None:
        raise HTTPException(status_code=503, detail="用户服务尚未配置")
    return value


@router.get("/users")
async def users(request: Request, q: str = Query("", max_length=200)):
    return {"success": True, "users": await store(request).find_users(q)}


@router.post("/users/{user_id}/quota")
async def adjust_quota(user_id: str, body: QuotaAdjustment, request: Request):
    try:
        user = await store(request).adjust_quota(user_id, body.resource, body.delta, body.reason.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400 if "not found" not in str(exc).lower() else 404, detail=str(exc)) from exc
    return {"success": True, "user": user}


@router.post("/users/{user_id}/quota/repair")
async def repair_quota(user_id: str, body: ReservationRepair, request: Request):
    try:
        user = await store(request).clear_reserved_quota(user_id, body.resource, body.reason.strip())
    except ValueError as exc:
        raise HTTPException(status_code=404 if "not found" in str(exc).lower() else 400, detail=str(exc)) from exc
    return {"success": True, "user": user}


@router.get("/users/{user_id}/quota/audit")
async def quota_audit(user_id: str, request: Request):
    return {"success": True, "events": await store(request).quota_audit(user_id)}


@router.get("/users/{user_id}/recharge")
async def recharge_history(user_id: str, request: Request):
    """获取用户的充值记录"""
    return {"success": True, "records": await store(request).recharge_history(user_id)}


@router.get("/payment-orders")
async def payment_orders(
    request: Request,
    status: str = Query("", pattern="^(pending|paid|expired|cancelled|refunded|failed|)$"),
):
    return {"success": True, "orders": await store(request).admin_payment_orders(status)}


@router.post("/payment-orders/{order_id}/query")
async def query_payment_order(order_id: str, request: Request):
    try:
        order = await store(request).admin_payment_order(order_id)
        provider = request.app.state.payment_registry.get(order["channel"])
        if provider is None:
            raise ValueError("Payment provider is not configured")
        result = await provider.query_order(order)
        if result.provider_order_id != order["provider_order_id"] or result.amount_fen != int(order["amount_fen"]):
            raise ValueError("Payment query mismatch")
        if result.status != "paid":
            return {"success": True, "status": result.status, "order": order}
        digest = hashlib.sha256(
            f"{result.provider_order_id}:{result.provider_trade_id}:{result.amount_fen}".encode()
        ).hexdigest()
        fulfilled = await store(request).fulfill_payment(
            order_id, order["channel"], f"query:{result.provider_trade_id}:paid", "TRADE_QUERY",
            result.provider_trade_id, result.amount_fen, digest, True,
        )
        return {"success": True, **fulfilled}
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/payment-orders/{order_id}/refund")
async def refund_payment_order(order_id: str, request: Request):
    try:
        order = await store(request).prepare_payment_refund(order_id)
        if order.get("status") == "refunded":
            return {"success": True, "status": "duplicate", "order": order}
        provider = request.app.state.payment_registry.get(order["channel"])
        if provider is None:
            raise ValueError("Payment provider is not configured")
        result = await provider.refund_order(order, order["refund_request_id"])
        if (
            result.provider_order_id != order["provider_order_id"]
            or result.refund_request_id != order["refund_request_id"]
            or result.amount_fen != int(order["amount_fen"])
        ):
            raise ValueError("Payment refund mismatch")
        refunded = await store(request).complete_payment_refund(
            order_id, result.refund_request_id, result.provider_trade_id
        )
        return {"success": True, **refunded}
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
