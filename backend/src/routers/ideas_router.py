"""Idea、会话和详情 API。"""

import logging
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request

from schemas.models import (
    DetailRequest,
    DetailResponse,
    GenerateRequest,
    GenerateResponse,
    SessionDetailResponse,
    SessionListResponse,
)
from services.idea_service import IdeaService
from services.agents.idea_agent import IdeaItem as AgentIdeaItem

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ideas"])


@router.post("/generate", response_model=GenerateResponse)
async def generate_ideas(request: Request, body: GenerateRequest):
    try:
        session = await request.app.state.idea_service.generate_ideas(
            direction=body.direction.strip(), count=body.count, category=body.category, model=body.model or ""
        )
        return GenerateResponse(
            success=True,
            session_id=session["id"],
            ideas=session["ideas"],
            total=len(session["ideas"]),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Idea generation failed")
        raise HTTPException(status_code=502, detail="模型生成失败，请检查配置后重试") from exc


@router.post("/detail", response_model=DetailResponse)
async def generate_detail(request: Request, body: DetailRequest):
    try:
        if body.idea is not None:
            idea = AgentIdeaItem(**body.idea.model_dump())
            try:
                plan = await request.app.state.idea_service.generate_detail_for_idea(idea, body.model or "")
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            idea_payload = asdict(idea)
        else:
            session = IdeaService.get_session(body.session_id)
            plan = await request.app.state.idea_service.generate_detail(
                body.session_id, body.idea_index, body.model or ""
            )
            idea_payload = session["ideas"][body.idea_index]
        return DetailResponse(
            success=True,
            idea=idea_payload,
            detailed_plan=plan,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("Detail generation failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions():
    return SessionListResponse(success=True, sessions=IdeaService.list_sessions())


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: str):
    try:
        return SessionDetailResponse(success=True, **IdeaService.get_session(session_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    if not IdeaService.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True}
