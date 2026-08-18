from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException, Response
from fastapi.testclient import TestClient

from routers.admin_router import router as admin_router
import routers.auth_router as auth_router_module
from routers.auth_router import (
    TokenExchange,
    _display_name,
    exchange_managed_token,
    providers,
    router as auth_router,
)
from routers.billing_router import router as billing_router
from routers.ideas_router import router as ideas_router


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


def test_retired_commercial_routes_are_not_registered():
    app = FastAPI()
    app.include_router(auth_router, prefix="/api")
    app.include_router(billing_router, prefix="/api")
    app.include_router(admin_router, prefix="/api")
    app.include_router(ideas_router, prefix="/api")
    client = TestClient(app)

    requests = [
        ("get", "/api/auth/login"),
        ("get", "/api/auth/callback?code=x&state=y"),
        ("get", "/api/billing/requests"),
        ("post", "/api/billing/requests"),
        ("get", "/api/admin/purchase-requests"),
        ("patch", "/api/admin/purchase-requests/request-1"),
        ("post", "/api/projects/import"),
    ]

    for method, path in requests:
        kwargs = {"json": {}} if method in {"post", "patch"} else {}
        assert getattr(client, method)(path, **kwargs).status_code == 404


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


@pytest.mark.asyncio
async def test_pending_deletion_requires_explicit_restore_before_session():
    store = SimpleNamespace(
        upsert_identity_user=AsyncMock(return_value={
            "id": "user-1", "status": "deletion_pending", "deletion_due_at": "2026-08-25T08:00:00Z",
        }),
        create_session=AsyncMock(),
    )
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        supabase_url="https://auth.example.test", supabase_anon_key="public-key", account_store=store,
        runtime_fetch=AsyncMock(return_value=FetchResponse({
            "id": "managed-1", "email": "person@example.com",
            "email_confirmed_at": "2026-08-13T00:00:00Z", "user_metadata": {},
        })),
    )))

    with pytest.raises(HTTPException) as error:
        await exchange_managed_token(request, TokenExchange(access_token="managed-token"), Response())

    assert error.value.status_code == 409
    assert error.value.detail["code"] == "account_deletion_pending"
    store.create_session.assert_not_awaited()


@pytest.mark.asyncio
async def test_explicit_restore_revalidates_identity_and_issues_session():
    restored_user = {
        "id": "user-1", "login": "person@example.com", "display_name": "Person", "avatar_url": "",
        "idea_limit": 5, "idea_used": 0, "idea_reserved": 0,
        "detail_limit": 2, "detail_used": 0, "detail_reserved": 0,
        "status": "active", "deletion_due_at": None,
    }
    store = SimpleNamespace(
        restore_account=AsyncMock(return_value=restored_user),
        create_session=AsyncMock(return_value="restored-session"),
        get_user_by_session=AsyncMock(return_value=restored_user),
    )
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        supabase_url="https://auth.example.test", supabase_anon_key="public-key", account_store=store,
        runtime_fetch=AsyncMock(return_value=FetchResponse({
            "id": "managed-1", "email": "person@example.com",
            "email_confirmed_at": "2026-08-13T00:00:00Z", "user_metadata": {},
        })),
    )))
    response = Response()

    result = await auth_router_module.restore_managed_account(
        request, TokenExchange(access_token="managed-token"), response
    )

    assert result["user"]["status"] == "active"
    store.restore_account.assert_awaited_once_with("supabase", "managed-1")
    assert "restored-session" in response.headers["set-cookie"]


@pytest.mark.asyncio
async def test_provider_config_exposes_turnstile_site_key_but_no_secret():
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        supabase_url="https://auth.example.test", supabase_anon_key="public-key",
        supabase_providers={"email": True}, turnstile_site_key="public-site-key",
        turnstile_secret_key="must-not-leak",
    )))

    result = await providers(request)

    assert result["turnstile_site_key"] == "public-site-key"
    assert "must-not-leak" not in str(result)
