import importlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

@pytest.mark.asyncio
async def test_export_is_downloadable_json_from_authenticated_user():
    account_router = importlib.import_module("routers.account_router")
    store = SimpleNamespace(export_account=AsyncMock(return_value={"profile": {"login": "person@example.com"}}))
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(account_store=store)))

    response = await account_router.export_account(request, {"id": "user-1"})

    assert response.headers["content-disposition"].startswith("attachment;")
    assert json.loads(response.body)["profile"]["login"] == "person@example.com"
    store.export_account.assert_awaited_once_with("user-1")


@pytest.mark.asyncio
async def test_deletion_requires_exact_confirmation_phrase():
    account_router = importlib.import_module("routers.account_router")
    store = SimpleNamespace(request_account_deletion=AsyncMock())
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(account_store=store)))

    with pytest.raises(HTTPException) as error:
        await account_router.request_deletion(
            account_router.DeletionRequest(confirmation="delete"), request, {"id": "user-1"}
        )

    assert error.value.status_code == 400
    store.request_account_deletion.assert_not_awaited()


@pytest.mark.asyncio
async def test_supabase_identity_delete_uses_server_secret_only():
    account_router = importlib.import_module("routers.account_router")
    response = SimpleNamespace(status=204)
    runtime_fetch = AsyncMock(return_value=response)
    state = SimpleNamespace(
        supabase_url="https://auth.example.test",
        supabase_secret_key="server-secret",
        runtime_fetch=runtime_fetch,
    )

    await account_router.delete_supabase_identity(state, "managed-user-id")

    _, options = runtime_fetch.await_args.args[0], runtime_fetch.await_args.kwargs
    assert options["method"] == "DELETE"
    assert options["headers"] == {
        "apikey": "server-secret",
        "Authorization": "Bearer server-secret",
    }
    assert "managed-user-id" in runtime_fetch.await_args.args[0]
