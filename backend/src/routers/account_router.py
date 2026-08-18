"""Account export and recoverable deletion lifecycle."""

import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from routers.config_router import require_config_admin
from services.auth import current_user

router = APIRouter(tags=["account"])


class DeletionRequest(BaseModel):
    confirmation: str = Field(..., min_length=1, max_length=20)


async def export_account(request: Request, user=Depends(current_user)):
    try:
        payload = await request.app.state.account_store.export_account(user["id"])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        json.dumps(payload, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=idea-spark-export.json"},
    )


@router.get("/account/export")
async def export_account_route(request: Request, user=Depends(current_user)):
    return await export_account(request, user)


@router.post("/account/deletion")
async def request_deletion(body: DeletionRequest, request: Request, user=Depends(current_user)):
    if body.confirmation != "注销我的账号":
        raise HTTPException(status_code=400, detail="请输入“注销我的账号”确认")
    try:
        account = await request.app.state.account_store.request_account_deletion(user["id"])
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"success": True, "status": account["status"], "deletion_due_at": account["deletion_due_at"]}


async def delete_supabase_identity(state, subject: str) -> None:
    secret = getattr(state, "supabase_secret_key", "")
    url = getattr(state, "supabase_url", "")
    runtime_fetch = getattr(state, "runtime_fetch", None)
    if not secret or not url or runtime_fetch is None:
        raise RuntimeError("Supabase identity deletion is not configured")
    response = await runtime_fetch(
        f"{url}/auth/v1/admin/users/{subject}",
        method="DELETE",
        headers={"apikey": secret, "Authorization": f"Bearer {secret}"},
    )
    if response.status not in {200, 204, 404}:
        raise RuntimeError(f"Supabase identity deletion failed ({response.status})")


@router.post("/admin/account-deletions/process", dependencies=[Depends(require_config_admin)])
async def process_account_deletions(request: Request):
    async def delete_identity(subject: str):
        await delete_supabase_identity(request.app.state, subject)

    result = await request.app.state.account_store.process_due_deletions(delete_identity)
    return {"success": True, **result}
