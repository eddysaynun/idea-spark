"""
配置管理路由
"""

from fastapi import APIRouter, Depends, Request
from typing import Annotated
from schemas.models import ConfigRequest, ConfigResponse, DetectModelsResponse

router = APIRouter(tags=["config"])

# 依赖注入 - 从 request 获取 app state
def get_model_client(request: Request):
    """从请求获取 model_client"""
    return request.app.state.model_client


@router.get("/config", response_model=ConfigResponse)
async def get_config(model_client = Depends(get_model_client)):
    """获取当前配置"""
    config_dict = {
        "provider": model_client.config.provider,
        "hermes_url": model_client.config.hermes_url,
        "openai_model": model_client.config.openai_model,
        "custom_base_url": model_client.config.custom_base_url,
        "custom_model": model_client.config.custom_model,
        "custom_api_key": model_client.config.custom_api_key,
        "temperature": model_client.config.temperature,
        "max_tokens": model_client.config.max_tokens
    }
    return ConfigResponse(success=True, config=config_dict)


@router.post("/config", response_model=ConfigResponse)
async def update_config(request: ConfigRequest, model_client = Depends(get_model_client)):
    """更新配置"""
    import json
    import os
    new_config = request.dict(exclude_unset=True)
    model_client.update_config(new_config)
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
    full_config = {
        "provider": model_client.config.provider,
        "hermes_url": model_client.config.hermes_url,
        "openai_api_key": model_client.config.openai_api_key,
        "openai_model": model_client.config.openai_model,
        "custom_base_url": model_client.config.custom_base_url,
        "custom_model": model_client.config.custom_model,
        "custom_api_key": model_client.config.custom_api_key,
        "temperature": model_client.config.temperature,
        "max_tokens": model_client.config.max_tokens
    }
    
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(full_config, f, indent=2, ensure_ascii=False)
    
    return ConfigResponse(success=True, config=full_config)


@router.get("/detect-models", response_model=DetectModelsResponse)
async def detect_models(model_client = Depends(get_model_client)):
    """检测 Custom API 支持的模型列表"""
    try:
        models = await model_client.detect_models()
        return DetectModelsResponse(success=True, models=models)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Model detection failed: {e}")
        return DetectModelsResponse(success=False, models=[])
