"""Managed multi-provider authentication and commercial account sessions."""

import json
import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from services.account_store import AccountStore
from services.auth import SESSION_COOKIE, current_user
from utils.http_client import request_text

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenExchange(BaseModel):
    access_token: str


def _display_name(metadata: dict, email: str) -> str:
    candidate = str(metadata.get("username") or metadata.get("full_name") or metadata.get("name") or "").strip()
    if 2 <= len(candidate) <= 32 and re.fullmatch(r"[\w\- ]+", candidate, flags=re.UNICODE):
        return candidate
    return email.split("@")[0][:32] or "Idea Spark 用户"


def _account_store(request: Request):
    store = getattr(request.app.state, "account_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="用户服务尚未配置")
    return store


def _supabase_config(request: Request):
    url = getattr(request.app.state, "supabase_url", "")
    anon_key = getattr(request.app.state, "supabase_anon_key", "")
    if not url or not anon_key:
        raise HTTPException(status_code=503, detail="邮箱及联合登录尚未配置")
    return url, anon_key


async def _fetch_json(request: Request, url: str, *, method: str = "GET", headers=None, body=None):
    runtime_fetch = getattr(request.app.state, "runtime_fetch", None)
    if runtime_fetch is not None:
        response = await runtime_fetch(url, method=method, headers=headers or {}, body=body)
        data = await response.json()
        return response.status, data
    status, text = await request_text(url, method=method, headers=headers, body=body, timeout=20)
    return status, json.loads(text)


async def _verified_profile(request: Request, access_token: str) -> dict:
    url, anon_key = _supabase_config(request)
    token = access_token.strip()
    if not token or len(token) > 8192:
        raise HTTPException(status_code=400, detail="登录凭据无效")
    status, profile = await _fetch_json(
        request,
        f"{url}/auth/v1/user",
        headers={"apikey": anon_key, "Authorization": f"Bearer {token}"},
    )
    if status != 200 or not profile.get("id"):
        raise HTTPException(status_code=401, detail="登录凭据无效或已过期")
    if profile.get("email") and not profile.get("email_confirmed_at"):
        raise HTTPException(status_code=403, detail="请先完成邮箱验证")
    return profile


async def _issue_session(store, user: dict, response: Response):
    session_token = await store.create_session(user["id"])
    response.set_cookie(
        SESSION_COOKIE, session_token, max_age=30 * 86400, httponly=True,
        secure=True, samesite="lax", path="/",
    )
    return {"success": True, "user": AccountStore.public_user(await store.get_user_by_session(session_token))}


@router.get("/providers")
async def providers(request: Request):
    """Return only public auth configuration; provider secrets never leave the Worker."""
    supabase_url = getattr(request.app.state, "supabase_url", "")
    supabase_key = getattr(request.app.state, "supabase_anon_key", "")
    configured = bool(supabase_url and supabase_key)
    enabled = getattr(request.app.state, "supabase_providers", {})
    return {
        "success": True,
        "turnstile_site_key": getattr(request.app.state, "turnstile_site_key", ""),
        "supabase": {
            "configured": configured,
            "url": supabase_url if configured else "",
            "anon_key": supabase_key if configured else "",
            "providers": {name: configured and bool(value) for name, value in enabled.items()},
        },
    }


@router.post("/exchange")
async def exchange_managed_token(request: Request, payload: TokenExchange, response: Response):
    """Validate a short-lived Supabase token, then issue the app's opaque HttpOnly session."""
    profile = await _verified_profile(request, payload.access_token)
    email = profile.get("email") or ""
    metadata = profile.get("user_metadata") or {}
    display_name = _display_name(metadata, email)
    avatar_url = metadata.get("avatar_url") or metadata.get("picture") or ""
    user = await _account_store(request).upsert_identity_user(
        "supabase", str(profile["id"]), email or str(profile["id"]), display_name, avatar_url
    )
    if user.get("status") == "deletion_pending":
        raise HTTPException(status_code=409, detail={
            "code": "account_deletion_pending",
            "deletion_due_at": user.get("deletion_due_at"),
        })
    if user.get("status", "active") != "active":
        raise HTTPException(status_code=403, detail={"code": "account_unavailable"})
    return await _issue_session(_account_store(request), user, response)


@router.post("/restore")
async def restore_managed_account(request: Request, payload: TokenExchange, response: Response):
    profile = await _verified_profile(request, payload.access_token)
    try:
        user = await _account_store(request).restore_account("supabase", str(profile["id"]))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return await _issue_session(_account_store(request), user, response)


@router.get("/me")
async def me(user=Depends(current_user)):
    return {"success": True, "user": AccountStore.public_user(user)}


@router.post("/logout")
async def logout(request: Request, response: Response):
    await _account_store(request).delete_session(request.cookies.get(SESSION_COOKIE, ""))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"success": True}
