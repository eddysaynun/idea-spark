import pytest
from fastapi import Request
from pydantic import ValidationError

from routers.ideas_router import generate_detail
from schemas.models import DetailRequest, GenerateRequest, IdeaItem


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


def test_detail_request_only_requires_server_owned_project_reference():
    request = DetailRequest(session_id="existing-session", idea_index=1)

    assert request.session_id == "existing-session"


def test_generate_request_can_consume_final_remaining_idea():
    assert GenerateRequest(direction="最后一次验证", count=1).count == 1


def test_idea_snapshot_rejects_empty_required_content():
    payload = idea_payload()
    payload["solution"] = ""

    with pytest.raises(ValidationError):
        IdeaItem(**payload)


class CachedProjectStore:
    def __init__(self):
        self.reserve_calls = 0

    async def get_project(self, user_id, project_id):
        assert user_id == "user-1"
        assert project_id == "project-1"
        return {"ideas": [idea_payload()], "detailed_plans": {"0": "already generated"}}

    async def reserve_quota(self, *args):
        self.reserve_calls += 1
        return "reserved"


async def test_cached_detail_does_not_consume_quota():
    store = CachedProjectStore()
    request = Request({"type": "http", "app": type("App", (), {"state": type("State", (), {"account_store": store})()})()})

    response = await generate_detail(
        request,
        DetailRequest(session_id="project-1", idea_index=0),
        user={"id": "user-1"},
        idempotency_key="detail-request-key-0001",
    )

    assert response.detailed_plan == "already generated"
    assert store.reserve_calls == 0


class DetailStore:
    async def get_project(self, _user_id, _project_id):
        return {"ideas": [idea_payload()], "detailed_plans": {}, "model": "model"}

    async def reserve_quota(self, *_args):
        return "reserved"

    async def save_plan(self, *_args):
        return None

    async def settle_quota(self, *_args):
        return None


class DetailModel:
    def validate_model(self, model):
        return model

    async def generate(self, _prompt, _model=None, **_options):
        return "# 落地方案\n\n" + "可执行内容。" * 40


async def test_detail_route_uses_model_client_without_legacy_idea_service():
    state = type("State", (), {
        "account_store": DetailStore(),
        "model_client": DetailModel(),
    })()
    request = Request({"type": "http", "app": type("App", (), {"state": state})()})

    response = await generate_detail(
        request,
        DetailRequest(session_id="project-1", idea_index=0),
        user={"id": "user-1"},
        idempotency_key="detail-request-key-0002",
    )

    assert response.detailed_plan.startswith("# 落地方案")
