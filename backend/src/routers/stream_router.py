"""三阶段生成流水线的 SSE 接口。"""

import json
import logging
from typing import AsyncGenerator, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from services.agents.idea_agent import IdeaItem
from services.agents.idea_pipeline import IdeaPipeline
from services.idea_service import IdeaService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["stream"])


def sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.get("/generate-stream")
async def generate_ideas_stream(
    request: Request,
    direction: str = Query(..., min_length=2, max_length=500),
    count: int = Query(5, ge=3, le=12),
    category: Literal["general", "ai-agent", "dev-tools", "privacy", "productivity"] = "general",
    model: str = Query("", max_length=200),
):
    try:
        selected_model = request.app.state.model_client.validate_model(model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    async def event_generator() -> AsyncGenerator[str, None]:
        session = IdeaService.create_session(direction.strip(), count, category, selected_model)
        ideas = []
        yield sse({"type": "start", "data": {"session_id": session["id"], "direction": direction}})
        try:
            pipeline = IdeaPipeline(request.app.state.model_client, selected_model)
            async for event in pipeline.run_events(direction.strip(), count, category):
                if event["type"] == "idea":
                    ideas.append(IdeaItem(**event["data"]))
                yield sse(event)

            IdeaService.complete_session(session["id"], ideas)
            yield sse({"type": "complete", "data": {"total": len(ideas), "session_id": session["id"]}})
        except Exception:
            IdeaService.sessions.pop(session["id"], None)
            logger.exception("Idea pipeline failed")
            yield sse({"type": "error", "data": {"message": "生成流程未能完成，请检查模型配置后重试"}})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
