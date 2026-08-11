"""
FastAPI Application - Idea Spark Backend
"""

import logging
import json
import os
from contextlib import asynccontextmanager
from dataclasses import asdict

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 初始化日志系统
    setup_logging("idea-spark")
    
    logger.info("🚀 Idea Spark Server starting...")
    
    # 加载配置
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                saved_config = json.load(f)
            app.state.model_config = ModelConfig(**saved_config)
            logger.info("✅ Loaded model config from file")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            app.state.model_config = ModelConfig()
    else:
        app.state.model_config = ModelConfig()
    
    app.state.model_client = ModelClient(app.state.model_config)
    logger.info(f"🔧 Model provider: {app.state.model_config.provider}")
    
    # 初始化 IdeaService
    from services.idea_service import IdeaService
    app.state.idea_service = IdeaService(app.state.model_client)
    logger.info("✅ IdeaService initialized")
    
    yield
    
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
    allow_origins=["*"],
    allow_credentials=True,
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
