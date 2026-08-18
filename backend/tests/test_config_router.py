import pytest
import httpx
from fastapi import HTTPException, Request
from fastapi import FastAPI

from services.models.model_client import ModelClient, ModelConfig
from routers.config_router import require_config_admin, router


@pytest.mark.asyncio
async def test_retired_model_config_endpoints_are_not_exposed():
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api")
    test_app.state.admin_token = "server-secret"
    test_app.state.model_client = ModelClient(ModelConfig())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        assert (await client.get("/api/config")).status_code == 404
        assert (await client.post("/api/config", json={"model": "other"})).status_code == 404
        assert (await client.get("/api/detect-models")).status_code == 404


def make_request(host: str, headers=None) -> Request:
    request = Request(
        {
            "type": "http",
            "client": (host, 1234) if host else None,
            "headers": headers or [],
            "app": FastAPI(),
        }
    )
    request.app.state.admin_token = None
    return request


def test_config_admin_requires_matching_token_for_remote_access(monkeypatch):
    monkeypatch.setenv("IDEA_SPARK_ADMIN_TOKEN", "server-secret")

    require_config_admin(make_request("203.0.113.10"), "server-secret")
    with pytest.raises(HTTPException) as error:
        require_config_admin(make_request("203.0.113.10"), "wrong")

    assert error.value.status_code == 401


def test_config_admin_without_token_only_allows_local_access(monkeypatch):
    monkeypatch.delenv("IDEA_SPARK_ADMIN_TOKEN", raising=False)

    require_config_admin(make_request("127.0.0.1"))
    with pytest.raises(HTTPException) as error:
        require_config_admin(make_request("203.0.113.10"))

    assert error.value.status_code == 503


def test_config_admin_uses_worker_runtime_secret(monkeypatch):
    monkeypatch.delenv("IDEA_SPARK_ADMIN_TOKEN", raising=False)
    request = make_request("203.0.113.10")
    request.app.state.admin_token = "worker-secret"

    require_config_admin(request, "worker-secret")
    with pytest.raises(HTTPException) as error:
        require_config_admin(request, "wrong")

    assert error.value.status_code == 401


def test_config_admin_without_client_scope_treats_cloudflare_request_as_remote(monkeypatch):
    monkeypatch.delenv("IDEA_SPARK_ADMIN_TOKEN", raising=False)
    request = make_request(
        "",
        headers=[(b"cf-connecting-ip", b"203.0.113.10")],
    )

    with pytest.raises(HTTPException) as error:
        require_config_admin(request)

    assert error.value.status_code == 503
