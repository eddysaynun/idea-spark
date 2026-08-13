"""User-visible quota packages and purchase-interest requests."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from services.auth import current_user

router = APIRouter(prefix="/billing", tags=["billing"])

PACKAGES = {
    "starter": {"id": "starter", "name": "Starter", "idea_amount": 20, "detail_amount": 5},
    "builder": {"id": "builder", "name": "Builder", "idea_amount": 60, "detail_amount": 20},
    "studio": {"id": "studio", "name": "Studio", "idea_amount": 150, "detail_amount": 50},
}


class PurchaseRequest(BaseModel):
    package_id: str = Field(..., min_length=2, max_length=40)
    note: str = Field("", max_length=300)


@router.get("/packages")
async def packages(_user=Depends(current_user)):
    return {"success": True, "packages": list(PACKAGES.values()), "payment_mode": "manual_review"}


@router.get("/requests")
async def requests(request: Request, user=Depends(current_user)):
    return {"success": True, "requests": await request.app.state.account_store.list_purchase_requests(user["id"])}


@router.post("/requests")
async def create_request(body: PurchaseRequest, request: Request, user=Depends(current_user)):
    package = PACKAGES.get(body.package_id)
    if package is None:
        raise HTTPException(status_code=400, detail="额度包不存在")
    purchase = await request.app.state.account_store.create_purchase_request(
        user["id"], package["id"], package["idea_amount"], package["detail_amount"], body.note.strip()
    )
    return {"success": True, "request": purchase}
