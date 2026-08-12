import pytest
from fastapi import HTTPException, Request

from services.models.model_client import ModelClient, ModelConfig
from routers.config_router import public_config, require_config_admin, update_config
from schemas.models import ConfigRequest


def test_public_config_never_exposes_api_keys():
    client = ModelClient(
        ModelConfig(api_key="model-secret")
    )

    config = public_config(client)

    assert "api_key" not in config
    assert config["has_api_key"] is True
    assert config["persistence"] == "memory"


def make_request(host: str) -> Request:
    return Request({"type": "http", "client": (host, 1234), "headers": []})


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


@pytest.mark.asyncio
async def test_update_config_only_changes_process_memory():
    client = ModelClient(ModelConfig())

    response = await update_config(
        ConfigRequest(base_url="https://model.example/v1", model="qwen3.5-27b"),
        _admin=None,
        model_client=client,
    )

    assert response.success is True
    assert client.config.base_url == "https://model.example/v1"
    assert client.config.model == "qwen3.5-27b"
    assert response.config["persistence"] == "memory"
