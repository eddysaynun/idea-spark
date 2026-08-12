"""
FastAPI Application - Idea Spark Backend
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from services.models.model_client import ModelClient, ModelConfig
from routers.config_router import router as config_router
from routers.ideas_router import router as ideas_router
from routers.stream_router import router as stream_router

from utils.logger import setup_logging
logger = logging.getLogger(__name__)

# 全局状态
sessions = {}


def load_model_config_from_env() -> ModelConfig:
    """从进程环境初始化模型配置，不读取或写入本地配置文件。"""
    config = ModelConfig()
    string_fields = {
        "base_url": "IDEA_SPARK_MODEL_BASE_URL",
        "model": "IDEA_SPARK_MODEL_NAME",
        "api_key": "IDEA_SPARK_MODEL_API_KEY",
    }
    for field_name, env_name in string_fields.items():
        if env_name in os.environ:
            setattr(config, field_name, os.environ[env_name])

    numeric_fields = {
        "temperature": ("IDEA_SPARK_MODEL_TEMPERATURE", float),
        "max_tokens": ("IDEA_SPARK_MODEL_MAX_TOKENS", int),
        "timeout": ("IDEA_SPARK_MODEL_TIMEOUT", int),
    }
    for field_name, (env_name, converter) in numeric_fields.items():
        if env_name not in os.environ:
            continue
        try:
            setattr(config, field_name, converter(os.environ[env_name]))
        except ValueError:
            logger.warning("Ignoring invalid numeric environment variable: %s", env_name)

    return config

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 初始化日志系统
    setup_logging("idea-spark")
    
    logger.info("🚀 Idea Spark Server starting...")
    
    # 只从环境变量初始化；运行时修改仅保存在当前进程内存中。
    app.state.model_config = load_model_config_from_env()
    
    app.state.model_client = ModelClient(app.state.model_config)
    logger.info("🔧 Default model: %s", app.state.model_config.model)
    
    # 初始化 IdeaService
    from services.idea_service import IdeaService
    app.state.idea_service = IdeaService(app.state.model_client)
    logger.info("✅ IdeaService initialized")
    
    yield

    await app.state.model_client.close()
    
    logger.info("👋 Idea Spark Server shutting down...")

# 创建 FastAPI 应用
app = FastAPI(
    title="Idea Spark API",
    description="AI-powered idea generation service",
    version="2.0.0",
    lifespan=lifespan
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.environ.get(
            "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if origin.strip()
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
static_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")
    logger.info(f"📁 Static files mounted from: {static_path}")

# 注册路由
app.include_router(config_router, prefix="/api")
app.include_router(ideas_router, prefix="/api")
app.include_router(stream_router, prefix="/api")

# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": __import__("datetime").datetime.now().isoformat()}

# 首页
@app.get("/")
async def index():
    from fastapi.responses import HTMLResponse
    index_path = os.path.join(static_path, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    raise HTTPException(status_code=404, detail="Index not found")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3001))
    logger.info(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
