"""Minimal first-party product action events without generated content."""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from services.auth import current_user

router = APIRouter(prefix="/product-events", tags=["product-events"])


class ProductEventRequest(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=100)
    idea_index: Optional[int] = Field(None, ge=0)
    action: Literal["expand", "export", "no_value"]


@router.post("")
async def record_product_event(
    body: ProductEventRequest,
    request: Request,
    user=Depends(current_user),
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=16, max_length=200),
):
    try:
        status = await request.app.state.account_store.record_product_event(
            user["id"], body.project_id, body.idea_index, body.action, idempotency_key
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "status": status}
