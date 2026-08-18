"""Audited commercial-account administration endpoints."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from routers.config_router import require_config_admin
from services.payment_reconciliation import query_and_fulfill, refund_prepared

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


@router.get("/metrics")
async def metrics(request: Request, days: int = Query(30, ge=1, le=90)):
    return {"success": True, "metrics": await store(request).admin_metrics(days)}


@router.post("/payment-orders/{order_id}/query")
async def query_payment_order(order_id: str, request: Request):
    try:
        return await query_and_fulfill(order_id, store(request), request.app.state.payment_registry)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/payment-orders/{order_id}/refund")
async def refund_payment_order(order_id: str, request: Request):
    try:
        order = await store(request).prepare_payment_refund(order_id)
        return await refund_prepared(order, store(request), request.app.state.payment_registry)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
