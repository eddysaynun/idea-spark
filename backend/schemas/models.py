"""
Pydantic 数据模型定义
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============ Config Schema ============

class ConfigRequest(BaseModel):
    """配置请求"""
    provider: str = Field("hermes", description="模型提供商")
    hermes_url: Optional[str] = Field(None, description="Hermes URL")
    openai_api_key: Optional[str] = Field(None, description="OpenAI API Key")
    custom_base_url: Optional[str] = Field(None, description="Custom Base URL")
    custom_model: Optional[str] = Field(None, description="Custom Model (auto = 自动检测)")
    custom_api_key: Optional[str] = Field(None, description="Custom API Key")
    temperature: Optional[float] = Field(None, ge=0, le=2, description="Temperature")


class ConfigResponse(BaseModel):
    """配置响应"""
    success: bool
    config: Dict[str, Any]


# ============ Ideas Schema ============

class IdeaItem(BaseModel):
    """单个 Idea"""
    name: str
    tagline: str
    pain_point: str
    solution: str
    target_user: str
    market_size: str
    competitors: str
    pricing: str
    revenue: str
    tech_stack: str
    advantage: str
    score: float
    tags: List[str]


class GenerateRequest(BaseModel):
    """生成 Ideas 请求"""
    direction: str = Field("", description="项目方向")
    count: int = Field(10, ge=5, le=20, description="生成数量")
    category: str = Field("general", description="分类")


class GenerateResponse(BaseModel):
    """生成 Ideas 响应"""
    success: bool
    session_id: str
    ideas: List[Dict[str, Any]]
    total: int


class DetailRequest(BaseModel):
    """详细方案请求"""
    session_id: str = Field(..., description="会话 ID")
    idea_index: int = Field(..., ge=0, description="Idea 索引")


class DetailResponse(BaseModel):
    """详细方案响应"""
    success: bool
    idea: Dict[str, Any]
    detailed_plan: str


# ============ Session Schema ============

class SessionInfo(BaseModel):
    """会话信息"""
    id: str
    direction: str
    category: str
    count: int
    created_at: str
    updated_at: str


class SessionListResponse(BaseModel):
    """会话列表响应"""
    success: bool
    sessions: List[SessionInfo]


class SessionDetailResponse(BaseModel):
    """会话详情响应"""
    success: bool
    direction: str
    count: int
    category: str
    ideas: List[Dict[str, Any]]
    created_at: str
    updated_at: str


# ============ Model Schema ============

class DetectModelsResponse(BaseModel):
    """检测模型响应"""
    success: bool
    models: List[str]


# ============ Common Schema ============

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    timestamp: str


class APIRootResponse(BaseModel):
    """API 根路径响应"""
    message: str
    version: str
