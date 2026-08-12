import pytest
from fastapi import FastAPI, Request
from pydantic import ValidationError

from routers.ideas_router import generate_detail
from schemas.models import DetailRequest, IdeaItem
from services.idea_service import IdeaService


def idea_payload():
    return {
        "name": "Snapshot Idea",
        "tagline": "跨实例生成详情",
        "pain_point": "Worker 内存不共享",
        "solution": "提交当前 Idea 快照",
        "target_user": "独立开发者",
        "market_size": "待验证",
        "competitors": "待验证",
        "pricing": "待验证",
        "revenue": "待验证",
        "tech_stack": "React + FastAPI",
        "advantage": "无状态",
        "score": 8.0,
        "tags": ["MVP"],
        "evidence": ["真实生成结果"],
        "assumptions": ["快照完整"],
        "risks": ["请求被篡改"],
        "confidence": "medium",
    }


def test_detail_request_accepts_validated_idea_snapshot():
    request = DetailRequest(session_id="missing-in-this-isolate", idea_index=0, idea=idea_payload())

    assert request.idea is not None
    assert request.idea.name == "Snapshot Idea"


@pytest.mark.parametrize(
    ("field", "value"),
    [("score", 11), ("confidence", "certain"), ("unexpected", "value")],
)
def test_detail_request_rejects_invalid_idea_snapshot(field, value):
    payload = idea_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        DetailRequest(session_id="session", idea_index=0, idea=payload)


def test_detail_request_keeps_session_only_compatibility():
    request = DetailRequest(session_id="existing-session", idea_index=1)

    assert request.idea is None


def test_idea_snapshot_rejects_empty_required_content():
    payload = idea_payload()
    payload["solution"] = ""

    with pytest.raises(ValidationError):
        IdeaItem(**payload)


async def test_detail_route_uses_snapshot_without_session_lookup(monkeypatch):
    class SnapshotService:
        async def generate_detail_for_idea(self, idea, model):
            assert idea.name == "Snapshot Idea"
            assert model == "selected-model"
            return "# 落地方案\n\n" + "可执行内容。" * 40

    def fail_session_lookup(_session_id):
        raise AssertionError("snapshot path must not read process memory")

    monkeypatch.setattr(IdeaService, "get_session", fail_session_lookup)
    app = FastAPI()
    app.state.idea_service = SnapshotService()
    request = Request({"type": "http", "app": app})

    response = await generate_detail(
        request,
        DetailRequest(
            session_id="missing-in-this-isolate",
            idea_index=0,
            model="selected-model",
            idea=idea_payload(),
        ),
    )

    assert response.success is True
    assert response.idea["name"] == "Snapshot Idea"
    assert response.detailed_plan.startswith("# 落地方案")
