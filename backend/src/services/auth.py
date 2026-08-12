"""Server-side authenticated session helpers."""

from typing import Dict

from fastapi import HTTPException, Request

SESSION_COOKIE = "idea_spark_session"


async def current_user(request: Request) -> Dict:
    store = getattr(request.app.state, "account_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="用户服务尚未配置")
    user = await store.get_user_by_session(request.cookies.get(SESSION_COOKIE, ""))
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return user
