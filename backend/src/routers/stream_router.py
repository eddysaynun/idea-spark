"""三阶段生成流水线的 SSE 接口。"""

import asyncio
import json
import logging
from typing import AsyncGenerator, AsyncIterator, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from services.agents.idea_agent import IdeaItem
from services.agents.idea_pipeline import IdeaPipeline
from schemas.models import GenerateRequest
from services.auth import current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["stream"])


def sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def with_heartbeat(
    source: AsyncIterator[dict], interval: float = 12.0
) -> AsyncGenerator[Optional[dict], None]:
    """等待长模型阶段时发出保活标记，不取消正在执行的模型请求。"""
    iterator = source.__aiter__()
    pending = None
    try:
        while True:
            if pending is None:
                pending = asyncio.create_task(anext(iterator))
            done, _ = await asyncio.wait({pending}, timeout=interval)
            if not done:
                yield None
                continue
            try:
                event = pending.result()
            except StopAsyncIteration:
                return
            pending = None
            yield event
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)


@router.post("/generate-stream")
async def generate_ideas_stream(
    request: Request,
    body: GenerateRequest,
    user=Depends(current_user),
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=16, max_length=200),
):
    try:
        selected_model = request.app.state.model_client.validate_model(body.model or "")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    reservation = await request.app.state.account_store.reserve_quota(
        user["id"], idempotency_key, "idea", body.count
    )
    if reservation == "duplicate":
        raise HTTPException(status_code=409, detail="请勿重复提交同一生成请求")
    if reservation == "denied":
        raise HTTPException(status_code=402, detail="免费 Idea 额度不足")
    try:
        project = await request.app.state.account_store.create_project(
            user["id"], body.direction.strip(), body.count, body.category, selected_model
        )
    except Exception:
        await request.app.state.account_store.settle_quota(
            user["id"], "", idempotency_key, "idea", body.count, False
        )
        raise

    async def event_generator() -> AsyncGenerator[str, None]:
        ideas = []
        try:
            yield sse({"type": "start", "data": {"session_id": project["id"], "direction": body.direction}})
            pipeline = IdeaPipeline(request.app.state.model_client, selected_model)
            events = pipeline.run_events(body.direction.strip(), body.count, body.category)
            async for event in with_heartbeat(events):
                if event is None:
                    yield ": heartbeat\n\n"
                    continue
                if event["type"] == "idea":
                    ideas.append(IdeaItem(**event["data"]))
                yield sse(event)

            payload = [vars(idea) for idea in ideas]
            await request.app.state.account_store.complete_project(user["id"], project["id"], payload)
            await request.app.state.account_store.settle_quota(
                user["id"], project["id"], idempotency_key, "idea", body.count, True
            )
            yield sse({"type": "complete", "data": {"total": len(ideas), "session_id": project["id"]}})
        except asyncio.CancelledError:
            project_id = project["id"]
            await request.app.state.account_store.fail_project(user["id"], project_id)
            await request.app.state.account_store.settle_quota(
                user["id"], project_id, idempotency_key, "idea", body.count, False
            )
            raise
        except Exception:
            project_id = project["id"]
            await request.app.state.account_store.fail_project(user["id"], project_id)
            await request.app.state.account_store.settle_quota(
                user["id"], project_id, idempotency_key, "idea", body.count, False
            )
            logger.exception("Idea pipeline failed")
            yield sse({"type": "error", "data": {"message": "生成流程未能完成，请检查模型配置后重试"}})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
