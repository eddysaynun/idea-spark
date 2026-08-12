"""GitHub OAuth and commercial account session API."""

from urllib.parse import urlencode

import aiohttp
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse

from services.account_store import AccountStore
from services.auth import SESSION_COOKIE, current_user

router = APIRouter(prefix="/auth", tags=["auth"])


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


@router.get("/login")
async def login(request: Request, return_to: str = Query("/", max_length=500)):
    client_id, _ = _oauth_config(request)
    store = _account_store(request)
    await store.delete_expired_auth_records()
    state = await store.create_oauth_state(return_to)
    callback = str(request.url_for("github_callback"))
    query = urlencode({"client_id": client_id, "redirect_uri": callback, "state": state, "scope": "read:user"})
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{query}", status_code=302)


@router.get("/callback", name="github_callback")
async def github_callback(request: Request, code: str = Query(...), state: str = Query(...)):
    client_id, client_secret = _oauth_config(request)
    store = _account_store(request)
    return_to = await store.consume_oauth_state(state)
    if return_to is None:
        raise HTTPException(status_code=400, detail="登录状态无效或已过期")
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={"client_id": client_id, "client_secret": client_secret, "code": code},
        ) as response:
            token_data = await response.json()
        access_token = token_data.get("access_token", "")
        if not access_token:
            raise HTTPException(status_code=401, detail="GitHub 登录失败")
        async with session.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json", "User-Agent": "Idea-Spark"},
        ) as response:
            profile = await response.json()
            if response.status != 200:
                raise HTTPException(status_code=401, detail="无法读取 GitHub 用户信息")
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
