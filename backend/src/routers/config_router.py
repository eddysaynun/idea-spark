"""受保护、仅进程内生效的模型配置 API。"""

import hmac
import os
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from schemas.models import ConfigRequest, ConfigResponse, DetectModelsResponse
from services.auth import current_user

router = APIRouter(tags=["config"])


def get_model_client(request: Request):
    return request.app.state.model_client


def require_config_admin(
    request: Request,
    x_admin_token: Optional[str] = Header(default=None),
) -> None:
    """公网必须使用管理员令牌；未配置令牌时仅允许本机访问。"""
    expected = getattr(request.app.state, "admin_token", None)
    if expected is None:
        expected = os.environ.get("IDEA_SPARK_ADMIN_TOKEN", "")
    if expected:
        if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
            raise HTTPException(status_code=401, detail="管理员令牌无效")
        return

    client_host = request.client.host if request.client else ""
    if not client_host:
        cf_connecting_ip = request.headers.get("CF-Connecting-IP", "")
        client_host = "127.0.0.1" if cf_connecting_ip in {"127.0.0.1", "::1"} else cf_connecting_ip
    if client_host not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(
            status_code=503,
            detail="公网配置管理未启用，请设置 IDEA_SPARK_ADMIN_TOKEN",
        )


def public_config(model_client) -> dict:
    """返回前端所需配置，永不回传密钥。"""
    config = model_client.config
    return {
        "base_url": config.base_url,
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "has_api_key": bool(config.api_key),
        "available_models": model_client.available_models(),
        "persistence": "memory",
    }


@router.get("/config", response_model=ConfigResponse)
async def get_config(
    _admin=Depends(require_config_admin),
    model_client=Depends(get_model_client),
):
    return ConfigResponse(success=True, config=public_config(model_client))


@router.post("/config", response_model=ConfigResponse)
async def update_config(
    body: ConfigRequest,
    _admin=Depends(require_config_admin),
    model_client=Depends(get_model_client),
):
    changes = body.model_dump(exclude_unset=True)
    for key in ("api_key",):
        if changes.get(key) == "":
            changes.pop(key)
    model_client.update_config(changes)
    return ConfigResponse(success=True, config=public_config(model_client))


@router.get("/detect-models", response_model=DetectModelsResponse)
async def detect_models(
    _admin=Depends(require_config_admin),
    model_client=Depends(get_model_client),
):
    models = await model_client.detect_models()
    return DetectModelsResponse(success=bool(models), models=models)


@router.get("/models", response_model=DetectModelsResponse)
async def list_models(
    _user=Depends(current_user),
    model_client=Depends(get_model_client),
):
    """向工作台公开可选择的模型名称，不暴露连接和密钥配置。"""
    models = model_client.available_models()
    return DetectModelsResponse(success=bool(models), models=models)
