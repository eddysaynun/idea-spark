"""Audited commercial-account administration endpoints."""

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
