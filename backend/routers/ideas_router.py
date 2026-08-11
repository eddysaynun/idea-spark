"""
Ideas 生成路由
"""

from fastapi import APIRouter, Depends, Request, HTTPException
from typing import Annotated
import logging
from schemas.models import GenerateRequest, GenerateResponse, SessionListResponse, SessionDetailResponse
from services.idea_service import IdeaService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ideas"])

# 依赖注入
def get_model_client(request: Request):
    """从请求获取 model_client"""
    return request.app.state.model_client


@router.post("/generate", response_model=GenerateResponse)
async def generate_ideas(
    request: Request,
    body: GenerateRequest
):
    """生成 Ideas"""
    try:
        idea_service = request.app.state.idea_service
        ideas = await idea_service.generate_ideas(
            direction=body.direction,
            count=body.count,
            category=body.category
        )
        
        # 转换为字典
        ideas_dict = [
            {
                "name": idea.name,
                "tagline": idea.tagline,
                "pain_point": idea.pain_point,
                "solution": idea.solution,
                "target_user": idea.target_user,
                "market_size": idea.market_size,
                "competitors": idea.competitors,
                "pricing": idea.pricing,
                "revenue": idea.revenue,
                "tech_stack": idea.tech_stack,
                "advantage": idea.advantage,
                "score": idea.score,
                "tags": idea.tags
            }
            for idea in ideas
        ]
        
        return GenerateResponse(
            success=True,
            session_id=ideas_dict[0]["name"] if ideas_dict else "",  # 简化处理
            ideas=ideas_dict,
            total=len(ideas_dict)
        )
    except Exception as e:
        logger.error(f"Generate failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions():
    """获取所有会话列表"""
    sessions = IdeaService.list_sessions()
    return SessionListResponse(
        success=True,
        sessions=[
            {
                "id": s["id"],
                "direction": s["direction"],
                "category": s["category"],
                "count": s["count"],
                "created_at": s["created_at"],
                "updated_at": s["updated_at"]
            }
            for s in sessions
        ]
    )


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: str):
    """获取会话详情"""
    try:
        session = IdeaService.get_session(session_id)
        return SessionDetailResponse(
            success=True,
            direction=session["direction"],
            count=session["count"],
            category=session["category"],
            ideas=session["ideas"],
            created_at=session["created_at"],
            updated_at=session["updated_at"]
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
