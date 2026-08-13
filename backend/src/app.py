"""FastAPI application for Idea Spark."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from services.models.model_client import ModelClient, ModelConfig
from routers.config_router import router as config_router
from routers.ideas_router import router as ideas_router
from routers.stream_router import router as stream_router
from routers.auth_router import router as auth_router
from routers.admin_router import router as admin_router
from routers.billing_router import router as billing_router

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


def load_model_config_from_bindings(env) -> ModelConfig:
    """从 Cloudflare Worker 绑定初始化配置，不进行持久化。"""
    config = ModelConfig()
    string_fields = {
        "base_url": "IDEA_SPARK_MODEL_BASE_URL",
        "model": "IDEA_SPARK_MODEL_NAME",
        "api_key": "IDEA_SPARK_MODEL_API_KEY",
    }
    for field_name, binding_name in string_fields.items():
        value = getattr(env, binding_name, None)
        if value is not None:
            setattr(config, field_name, str(value))

    numeric_fields = {
        "temperature": ("IDEA_SPARK_MODEL_TEMPERATURE", float),
        "max_tokens": ("IDEA_SPARK_MODEL_MAX_TOKENS", int),
        "timeout": ("IDEA_SPARK_MODEL_TIMEOUT", int),
    }
    for field_name, (binding_name, converter) in numeric_fields.items():
        value = getattr(env, binding_name, None)
        if value is None:
            continue
        try:
            setattr(config, field_name, converter(value))
        except (TypeError, ValueError):
            logger.warning("Ignoring invalid numeric Worker binding: %s", binding_name)

    return config


async def initialize_application(app: FastAPI, env=None) -> None:
    """幂等初始化本地 ASGI 与 Cloudflare Worker 共用的应用状态。"""
    if getattr(app.state, "idea_service", None) is not None:
        return
    config = load_model_config_from_bindings(env) if env is not None else load_model_config_from_env()
    app.state.model_config = config
    app.state.admin_token = (
        str(getattr(env, "IDEA_SPARK_ADMIN_TOKEN", ""))
        if env is not None
        else os.environ.get("IDEA_SPARK_ADMIN_TOKEN", "")
    )
    app.state.github_client_id = (
        str(getattr(env, "GITHUB_CLIENT_ID", ""))
        if env is not None else os.environ.get("GITHUB_CLIENT_ID", "")
    )
    app.state.github_client_secret = (
        str(getattr(env, "GITHUB_CLIENT_SECRET", ""))
        if env is not None else os.environ.get("GITHUB_CLIENT_SECRET", "")
    )
    app.state.supabase_url = (
        str(getattr(env, "SUPABASE_URL", "")).rstrip("/")
        if env is not None else os.environ.get("SUPABASE_URL", "").rstrip("/")
    )
    app.state.supabase_anon_key = (
        str(getattr(env, "SUPABASE_ANON_KEY", ""))
        if env is not None else os.environ.get("SUPABASE_ANON_KEY", "")
    )
    def binding(name: str, default: str = "") -> str:
        return str(getattr(env, name, default)) if env is not None else os.environ.get(name, default)
    app.state.supabase_providers = {
        "email": binding("AUTH_EMAIL_ENABLED", "true").lower() == "true",
        "github": binding("AUTH_GITHUB_ENABLED", "false").lower() == "true",
        "google": binding("AUTH_GOOGLE_ENABLED", "false").lower() == "true",
        "apple": binding("AUTH_APPLE_ENABLED", "false").lower() == "true",
    }
    model_proxy = getattr(env, "MODEL_PROXY", None) if env is not None else None
    app.state.model_client = ModelClient(config, service_binding=model_proxy)

    from services.idea_service import IdeaService

    app.state.idea_service = IdeaService(app.state.model_client)
    database = getattr(env, "DB", None) if env is not None else None
    if database is not None:
        from services.account_store import AccountStore
        idea_limit = int(str(getattr(env, "FREE_IDEA_LIMIT", "5")))
        detail_limit = int(str(getattr(env, "FREE_DETAIL_LIMIT", "2")))
        app.state.account_store = AccountStore(database, idea_limit, detail_limit)
    else:
        app.state.account_store = None
    logger.info("IdeaService initialized with model %s", config.model)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 初始化日志系统
    setup_logging("idea-spark")
    
    logger.info("🚀 Idea Spark Server starting...")
    
    # Python Worker 入口会先注入绑定；本地 ASGI 则从环境变量初始化。
    if getattr(app.state, "idea_service", None) is None:
        await initialize_application(app)
    
    yield

    if os.environ.get("IDEA_SPARK_RUNTIME") != "cloudflare":
        await app.state.model_client.close()
        app.state.idea_service = None
        app.state.model_client = None
    
    logger.info("👋 Idea Spark Server shutting down...")

# 创建 FastAPI 应用
app = FastAPI(
    title="Idea Spark API",
    description="AI-powered idea generation service",
    version="2.0.0",
    lifespan=lifespan,
    docs_url=None if os.environ.get("IDEA_SPARK_RUNTIME") == "cloudflare" else "/docs",
    openapi_url=None if os.environ.get("IDEA_SPARK_RUNTIME") == "cloudflare" else "/openapi.json",
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > 1_000_000:
                return JSONResponse(status_code=413, content={"detail": "请求体过大"})
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "无效的 Content-Length"})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' https://avatars.githubusercontent.com data:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self' https://*.supabase.co; "
        "font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self' https://github.com"
    )
    if request.url.path.startswith("/api/") and "cache-control" not in response.headers:
        response.headers["Cache-Control"] = "no-store"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

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
app.include_router(auth_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(billing_router, prefix="/api")
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
    import uvicorn

    port = int(os.environ.get("PORT", 3001))
    logger.info(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
