"""User-visible quota packages, payment orders and manual purchase requests."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from services.auth import current_user

router = APIRouter(prefix="/billing", tags=["billing"])

PACKAGES = {
    "starter": {"id": "starter", "name": "Starter", "idea_amount": 20, "detail_amount": 5, "amount_fen": 2900},
    "builder": {"id": "builder", "name": "Builder", "idea_amount": 60, "detail_amount": 20, "amount_fen": 7900},
    "studio": {"id": "studio", "name": "Studio", "idea_amount": 150, "detail_amount": 50, "amount_fen": 16900},
}


class PurchaseRequest(BaseModel):
    package_id: str = Field(..., min_length=2, max_length=40)
    note: str = Field("", max_length=300)


class PaymentOrderRequest(BaseModel):
    package_id: str = Field(..., min_length=2, max_length=40)
    channel: str = Field(..., pattern="^alipay$")


def registry(request: Request):
    return request.app.state.payment_registry


@router.get("/packages")
async def packages(request: Request, _user=Depends(current_user)):
    channels = registry(request).public_status()
    return {
        "success": True,
        "packages": list(PACKAGES.values()),
        "payment_mode": "online" if any(item["configured"] for item in channels.values()) else "manual_review",
        "channels": channels,
    }


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


@router.get("/orders")
async def orders(request: Request, user=Depends(current_user)):
    return {"success": True, "orders": await request.app.state.account_store.list_payment_orders(user["id"])}


@router.get("/orders/{order_id}")
async def order(order_id: str, request: Request, user=Depends(current_user)):
    try:
        value = await request.app.state.account_store.get_payment_order(user["id"], order_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="支付订单不存在") from exc
    return {"success": True, "order": value}


@router.post("/orders")
async def create_order(body: PaymentOrderRequest, request: Request, user=Depends(current_user)):
    package = PACKAGES.get(body.package_id)
    if package is None:
        raise HTTPException(status_code=400, detail="额度包不存在")
    provider = registry(request).get(body.channel)
    if provider is None:
        raise HTTPException(status_code=503, detail="该支付渠道正在完成商户认证，暂未开放")
    store = request.app.state.account_store
    created = await store.create_payment_order(user["id"], package, body.channel)
    try:
        checkout = await provider.create_checkout(created, str(request.base_url).rstrip("/"))
        created = await store.attach_payment_checkout(
            user["id"], created["id"], checkout["provider_order_id"], checkout["pay_url"]
        )
    except Exception as exc:
        await store.fail_payment_order(user["id"], created["id"], "provider checkout failed")
        raise HTTPException(status_code=502, detail="支付平台暂时无法创建订单，请稍后重试") from exc
    return {"success": True, "order": created}


@router.post("/webhooks/{channel}")
async def payment_webhook(channel: str, request: Request):
    if channel != "alipay":
        raise HTTPException(status_code=404, detail="支付渠道不存在")
    provider = registry(request).get(channel)
    if provider is None:
        raise HTTPException(status_code=503, detail="支付渠道尚未配置")
    body = await request.body()
    try:
        notice = await provider.verify_notification(dict(request.headers), body)
        store = request.app.state.account_store
        order_id = await store.payment_order_id_for_provider(channel, notice.provider_order_id)
        result = await store.fulfill_payment(
            order_id, channel, notice.event_key, notice.event_type,
            notice.provider_trade_id, notice.amount_fen, notice.payload_digest, True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if channel == "alipay":
        return Response(content="success", media_type="text/plain")
    return {"code": "SUCCESS", "message": result["status"]}
