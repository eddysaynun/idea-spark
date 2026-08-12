"""
Pydantic 数据模型定义
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Annotated, Optional, List, Dict, Any, Literal


IdeaListEntry = Annotated[str, Field(min_length=1, max_length=4000)]


# ============ Config Schema ============

class ConfigRequest(BaseModel):
    """配置请求"""
    base_url: Optional[str] = Field(None, min_length=8, max_length=500, description="OpenAI-compatible Base URL")
    model: Optional[str] = Field(None, min_length=1, max_length=200, description="默认模型")
    api_key: Optional[str] = Field(None, max_length=1000, description="API Key")
    temperature: Optional[float] = Field(None, ge=0, le=2, description="Temperature")


class ConfigResponse(BaseModel):
    """配置响应"""
    success: bool
    config: Dict[str, Any]


# ============ Ideas Schema ============

class IdeaItem(BaseModel):
    """单个 Idea"""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=200)
    tagline: str = Field(..., min_length=1, max_length=500)
    pain_point: str = Field(..., min_length=1, max_length=4000)
    solution: str = Field(..., min_length=1, max_length=4000)
    target_user: str = Field(..., min_length=1, max_length=2000)
    market_size: str = Field(..., min_length=1, max_length=4000)
    competitors: str = Field(..., min_length=1, max_length=4000)
    pricing: str = Field(..., min_length=1, max_length=2000)
    revenue: str = Field(..., min_length=1, max_length=2000)
    tech_stack: str = Field(..., min_length=1, max_length=2000)
    advantage: str = Field(..., min_length=1, max_length=4000)
    score: float = Field(..., ge=0, le=10)
    tags: List[IdeaListEntry] = Field(..., max_length=30)
    evidence: List[IdeaListEntry] = Field(default_factory=list, max_length=30)
    assumptions: List[IdeaListEntry] = Field(default_factory=list, max_length=30)
    risks: List[IdeaListEntry] = Field(default_factory=list, max_length=30)
    confidence: Literal["low", "medium", "high"] = "medium"


class GenerateRequest(BaseModel):
    """生成 Ideas 请求"""
    direction: str = Field(..., min_length=2, max_length=500, description="项目方向")
    count: int = Field(5, ge=1, le=12, description="生成数量")
    category: Literal["general", "ai-agent", "dev-tools", "privacy", "productivity"] = Field(
        "general", description="分类"
    )
    model: Optional[str] = Field(None, min_length=1, max_length=200, description="本次使用的模型")


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
    model: Optional[str] = Field(None, min_length=1, max_length=200, description="本次使用的模型")


class DetailResponse(BaseModel):
    """详细方案响应"""
    success: bool
    idea: Dict[str, Any]
    detailed_plan: str


class ImportProjectRequest(BaseModel):
    """显式导入旧版浏览器本地探索。"""
    idempotency_key: str = Field(..., min_length=16, max_length=200)
    direction: str = Field(..., min_length=2, max_length=500)
    count: int = Field(..., ge=1, le=12)
    category: Literal["general", "ai-agent", "dev-tools", "privacy", "productivity"] = "general"
    model: str = Field(..., min_length=1, max_length=200)
    ideas: List[IdeaItem] = Field(..., min_length=1, max_length=12)
    detailed_plans: Dict[str, str] = Field(default_factory=dict)


# ============ Session Schema ============

class SessionInfo(BaseModel):
    """会话信息"""
    id: str
    direction: str
    category: str
    count: int
    model: str = ""
    created_at: str
    updated_at: str


class SessionListResponse(BaseModel):
    """会话列表响应"""
    success: bool
    sessions: List[SessionInfo]


class SessionDetailResponse(BaseModel):
    """会话详情响应"""
    success: bool
    id: str
    direction: str
    count: int
    category: str
    model: str = ""
    ideas: List[Dict[str, Any]]
    created_at: str
    updated_at: str
    detailed_plans: Dict[str, str] = Field(default_factory=dict)


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
