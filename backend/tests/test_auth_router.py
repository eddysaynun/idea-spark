from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException, Request, Response

from routers.auth_router import TokenExchange, _display_name, _github_profile, exchange_managed_token


class FetchResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    async def json(self):
        return self.payload


@pytest.mark.parametrize("metadata,expected", [
    ({"username": "小陈 Builder"}, "小陈 Builder"),
    ({"username": "dev_user-7"}, "dev_user-7"),
    ({"username": "<script>"}, "person"),
    ({"username": "x"}, "person"),
])
def test_managed_display_name_prefers_valid_registration_username(metadata, expected):
    assert _display_name(metadata, "person@example.com") == expected


async def test_github_oauth_uses_worker_native_fetch():
    calls = []

    async def runtime_fetch(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("access_token"):
            return FetchResponse({"access_token": "short-lived-token"})
        return FetchResponse({"id": 7, "login": "octocat"})

    app = FastAPI()
    app.state.runtime_fetch = runtime_fetch
    request = Request({"type": "http", "app": app})

    profile = await _github_profile(request, "one-time-code", "client-id", "client-secret")

    assert profile["login"] == "octocat"
    assert calls[0][1]["method"] == "POST"
    assert calls[0][1]["body"] == "client_id=client-id&client_secret=client-secret&code=one-time-code"
    assert calls[1][1]["headers"]["Authorization"] == "Bearer short-lived-token"


@pytest.mark.asyncio
async def test_managed_token_is_verified_before_app_session():
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        supabase_url="https://auth.example.test",
        supabase_anon_key="public-key",
        runtime_fetch=None,
        account_store=SimpleNamespace(),
    )))
    store = request.app.state.account_store
    store.upsert_identity_user = AsyncMock(return_value={"id": "user-1"})
    store.create_session = AsyncMock(return_value="opaque-session")
    store.get_user_by_session = AsyncMock(return_value={
        "id": "user-1", "login": "person@example.com", "display_name": "Person", "avatar_url": "",
        "idea_limit": 5, "idea_used": 0, "idea_reserved": 0,
        "detail_limit": 2, "detail_used": 0, "detail_reserved": 0,
    })

    async def native_fetch(url, **kwargs):
        assert url == "https://auth.example.test/auth/v1/user"
        assert kwargs["headers"]["Authorization"] == "Bearer managed-token"
        return FetchResponse({
            "id": "managed-1", "email": "person@example.com",
            "email_confirmed_at": "2026-08-13T00:00:00Z", "user_metadata": {"name": "Person"},
        })

    request.app.state.runtime_fetch = native_fetch
    response = Response()
    result = await exchange_managed_token(request, TokenExchange(access_token="managed-token"), response)

    assert result["success"] is True
    store.upsert_identity_user.assert_awaited_once_with(
        "supabase", "managed-1", "person@example.com", "Person", ""
    )
    assert "idea_spark_session=" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]


@pytest.mark.asyncio
async def test_invalid_managed_token_does_not_create_account():
    store = SimpleNamespace(upsert_identity_user=AsyncMock(), create_session=AsyncMock())
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        supabase_url="https://auth.example.test", supabase_anon_key="public-key", account_store=store,
        runtime_fetch=lambda *args, **kwargs: None,
    )))

    async def denied(*args, **kwargs):
        response = FetchResponse({"message": "invalid"})
        response.status = 401
        return response

    request.app.state.runtime_fetch = denied
    with pytest.raises(HTTPException) as error:
        await exchange_managed_token(request, TokenExchange(access_token="bad-token"), Response())
    assert error.value.status_code == 401
    store.upsert_identity_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_unverified_email_cannot_receive_app_account():
    store = SimpleNamespace(upsert_identity_user=AsyncMock(), create_session=AsyncMock())
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        supabase_url="https://auth.example.test", supabase_anon_key="public-key", account_store=store,
    )))

    async def unverified(*args, **kwargs):
        return FetchResponse({"id": "managed-2", "email": "new@example.com", "email_confirmed_at": None})

    request.app.state.runtime_fetch = unverified
    with pytest.raises(HTTPException) as error:
        await exchange_managed_token(request, TokenExchange(access_token="unverified"), Response())
    assert error.value.status_code == 403
    store.upsert_identity_user.assert_not_awaited()
