"""Managed multi-provider authentication and commercial account sessions."""

import logging
import json
import re
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from fastapi.responses import RedirectResponse

from services.account_store import AccountStore
from services.auth import SESSION_COOKIE, current_user
from utils.http_client import request_text

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


class TokenExchange(BaseModel):
    access_token: str


def _display_name(metadata: dict, email: str) -> str:
    candidate = str(metadata.get("username") or metadata.get("full_name") or metadata.get("name") or "").strip()
    if 2 <= len(candidate) <= 32 and re.fullmatch(r"[\w\- ]+", candidate, flags=re.UNICODE):
        return candidate
    return email.split("@")[0][:32] or "Idea Spark 用户"


def _oauth_config(request: Request):
    client_id = getattr(request.app.state, "github_client_id", "")
    client_secret = getattr(request.app.state, "github_client_secret", "")
    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail="GitHub 登录尚未配置")
    return client_id, client_secret


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


async def _github_profile(request: Request, code: str, client_id: str, client_secret: str):
    """Exchange the OAuth code through the Worker-native fetch transport in production."""
    runtime_fetch = getattr(request.app.state, "runtime_fetch", None)
    if runtime_fetch is not None:
        token_response = await runtime_fetch(
            "https://github.com/login/oauth/access_token",
            method="POST",
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
            body=urlencode({"client_id": client_id, "client_secret": client_secret, "code": code}),
        )
        token_data = await token_response.json()
        access_token = token_data.get("access_token", "")
        if not access_token:
            raise HTTPException(status_code=401, detail="GitHub 登录失败")
        profile_response = await runtime_fetch(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "Idea-Spark",
            },
        )
        if profile_response.status != 200:
            raise HTTPException(status_code=401, detail="无法读取 GitHub 用户信息")
        return await profile_response.json()

    token_status, token_text = await request_text(
        "https://github.com/login/oauth/access_token",
        method="POST",
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        body=urlencode({"client_id": client_id, "client_secret": client_secret, "code": code}),
    )
    token_data = json.loads(token_text)
    access_token = token_data.get("access_token", "") if token_status == 200 else ""
    if not access_token:
        raise HTTPException(status_code=401, detail="GitHub 登录失败")
    profile_status, profile_text = await request_text(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json", "User-Agent": "Idea-Spark"},
    )
    if profile_status != 200:
        raise HTTPException(status_code=401, detail="无法读取 GitHub 用户信息")
    return json.loads(profile_text)


@router.get("/login")
async def login(request: Request, return_to: str = Query("/", max_length=500)):
    client_id, _ = _oauth_config(request)
    store = _account_store(request)
    await store.delete_expired_auth_records()
    state = await store.create_oauth_state(return_to)
    callback = str(request.url_for("github_callback"))
    query = urlencode({"client_id": client_id, "redirect_uri": callback, "state": state, "scope": "read:user"})
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{query}", status_code=302)


@router.get("/providers")
async def providers(request: Request):
    """Return only public auth configuration; provider secrets never leave the Worker."""
    supabase_url = getattr(request.app.state, "supabase_url", "")
    supabase_key = getattr(request.app.state, "supabase_anon_key", "")
    configured = bool(supabase_url and supabase_key)
    enabled = getattr(request.app.state, "supabase_providers", {})
    return {
        "success": True,
        "github": bool(getattr(request.app.state, "github_client_id", "")) and not configured,
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
    url, anon_key = _supabase_config(request)
    token = payload.access_token.strip()
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
    email = profile.get("email") or ""
    metadata = profile.get("user_metadata") or {}
    display_name = _display_name(metadata, email)
    avatar_url = metadata.get("avatar_url") or metadata.get("picture") or ""
    user = await _account_store(request).upsert_identity_user(
        "supabase", str(profile["id"]), email or str(profile["id"]), display_name, avatar_url
    )
    session_token = await _account_store(request).create_session(user["id"])
    response.set_cookie(
        SESSION_COOKIE, session_token, max_age=30 * 86400, httponly=True,
        secure=True, samesite="lax", path="/",
    )
    return {"success": True, "user": AccountStore.public_user(await _account_store(request).get_user_by_session(session_token))}


@router.get("/callback", name="github_callback")
async def github_callback(request: Request, code: str = Query(...), state: str = Query(...)):
    client_id, client_secret = _oauth_config(request)
    store = _account_store(request)
    return_to = await store.consume_oauth_state(state)
    if return_to is None:
        raise HTTPException(status_code=400, detail="登录状态无效或已过期")
    try:
        profile = await _github_profile(request, code, client_id, client_secret)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("GitHub OAuth exchange failed")
        raise HTTPException(status_code=502, detail="GitHub 登录服务暂时不可用") from exc
    user = await store.upsert_github_user(
        str(profile["id"]), profile["login"], profile.get("name") or profile["login"], profile.get("avatar_url") or ""
    )
    token = await store.create_session(user["id"])
    result = RedirectResponse(return_to, status_code=302)
    result.set_cookie(SESSION_COOKIE, token, max_age=30 * 86400, httponly=True, secure=True, samesite="lax", path="/")
    return result


@router.get("/me")
async def me(user=Depends(current_user)):
    return {"success": True, "user": AccountStore.public_user(user)}


@router.post("/logout")
async def logout(request: Request, response: Response):
    await _account_store(request).delete_session(request.cookies.get(SESSION_COOKIE, ""))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"success": True}
