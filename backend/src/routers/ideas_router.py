"""Idea、会话和详情 API。"""

import logging
from fastapi import APIRouter, Depends, Header, HTTPException, Request

from schemas.models import (
    DetailRequest,
    DetailResponse,
    ImportProjectRequest,
    SessionDetailResponse,
    SessionListResponse,
)
from services.agents.idea_agent import DetailGenerationAgent, IdeaItem as AgentIdeaItem
from services.auth import current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ideas"])


@router.post("/projects/import")
async def import_project(request: Request, body: ImportProjectRequest, user=Depends(current_user)):
    payload = body.model_dump()
    payload["ideas"] = [idea.model_dump() for idea in body.ideas]
    try:
        project = await request.app.state.account_store.import_project(user["id"], payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"success": True, "project": project}


@router.post("/detail", response_model=DetailResponse)
async def generate_detail(
    request: Request,
    body: DetailRequest,
    user=Depends(current_user),
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=16, max_length=200),
):
    try:
        project = await request.app.state.account_store.get_project(user["id"], body.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if body.idea_index >= len(project["ideas"]):
        raise HTTPException(status_code=404, detail="Idea not found")
    cached_plan = project["detailed_plans"].get(str(body.idea_index))
    if cached_plan:
        return DetailResponse(
            success=True,
            idea=project["ideas"][body.idea_index],
            detailed_plan=cached_plan,
        )
    try:
        selected_model = request.app.state.model_client.validate_model(
            body.model or project.get("model", "")
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    reservation = await request.app.state.account_store.reserve_quota(
        user["id"], idempotency_key, "detail", 1
    )
    if reservation == "duplicate":
        raise HTTPException(status_code=409, detail="请勿重复提交同一详细方案请求")
    if reservation == "denied":
        raise HTTPException(status_code=402, detail="免费详细方案额度不足")
    try:
        idea_payload = project["ideas"][body.idea_index]
        idea = AgentIdeaItem(**idea_payload)
        plan = await DetailGenerationAgent(
            request.app.state.model_client, selected_model, body.session_id
        ).generate_detail(idea)
        await request.app.state.account_store.save_plan(
            user["id"], body.session_id, body.idea_index, plan
        )
        await request.app.state.account_store.settle_quota(
            user["id"], body.session_id, idempotency_key, "detail", 1, True
        )
        return DetailResponse(
            success=True,
            idea=idea_payload,
            detailed_plan=plan,
        )
    except HTTPException:
        await request.app.state.account_store.settle_quota(
            user["id"], body.session_id, idempotency_key, "detail", 1, False
        )
        raise
    except ValueError as exc:
        await request.app.state.account_store.settle_quota(
            user["id"], body.session_id, idempotency_key, "detail", 1, False
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        await request.app.state.account_store.settle_quota(
            user["id"], body.session_id, idempotency_key, "detail", 1, False
        )
        logger.exception("Detail generation failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(request: Request, user=Depends(current_user)):
    sessions = await request.app.state.account_store.list_projects(user["id"])
    return SessionListResponse(success=True, sessions=sessions)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: str, request: Request, user=Depends(current_user)):
    try:
        return SessionDetailResponse(
            success=True,
            **await request.app.state.account_store.get_project(user["id"], session_id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, request: Request, user=Depends(current_user)):
    if not await request.app.state.account_store.delete_project(user["id"], session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True}
