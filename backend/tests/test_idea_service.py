import json

import pytest

from services.idea_service import IdeaService


class FakeModelClient:
    def __init__(self, repair_editor=False):
        self.generate_calls = 0
        self.repair_editor = repair_editor

    config = type("Config", (), {"model": "test-model"})()

    def validate_model(self, model):
        if model == "hidden-model":
            raise ValueError("所选模型不可用")
        return model or self.config.model

    async def generate_stream(self, _prompt, _model=None):
        payload = [
            {
                "name": f"Idea {index}",
                "tagline": "可验证机会",
                "pain_point": "真实痛点",
                "solution": "明确方案",
                "target_user": "独立开发者",
                "market_size": "细分市场",
                "competitors": "现有替代品",
                "pricing": "¥49/月",
                "revenue": "可量化收入",
                "tech_stack": "React + FastAPI",
                "advantage": "聚焦",
                "score": 8.0,
                "tags": ["MVP"],
            }
            for index in range(6)
        ]
        yield {"type": "content", "data": json.dumps(payload)}

    async def generate(self, _prompt, _model=None):
        self.generate_calls += 1
        if self.generate_calls == 1:
            return json.dumps([
                {
                    "candidate_index": index,
                    "pain_score": 8,
                    "differentiation_score": 7,
                    "feasibility_score": 8,
                    "monetization_score": 7,
                    "evidence_score": 6,
                    "fatal_flaw": "需要验证",
                    "missing_evidence": "用户访谈",
                    "recommendation": "keep",
                }
                for index in range(6)
            ])
        if self.repair_editor and self.generate_calls == 2:
            return "not-json"
        return json.dumps([
            {
                "name": f"Final Idea {index}",
                "tagline": "可验证机会",
                "pain_point": "真实痛点",
                "solution": "明确方案",
                "target_user": "独立开发者",
                "market_size": "待验证的细分市场",
                "competitors": "现有替代品",
                "pricing": "¥49/月，需访谈验证",
                "revenue": "取决于付费转化率",
                "tech_stack": "React + FastAPI",
                "advantage": "聚焦",
                "score": 8.0,
                "tags": ["MVP"],
                "evidence": ["访谈线索"],
                "assumptions": ["用户愿意付费", "问题高频"],
                "risks": ["需求不足", "获客成本高"],
                "confidence": "medium",
            }
            for index in range(3)
        ])


@pytest.fixture(autouse=True)
def clear_sessions():
    IdeaService.sessions.clear()
    yield
    IdeaService.sessions.clear()


async def test_generation_creates_retrievable_session():
    model_client = FakeModelClient()
    service = IdeaService(model_client)

    session = await service.generate_ideas("开发者验证工具", 3, "dev-tools")

    assert session["id"]
    assert len(session["ideas"]) == 3
    assert IdeaService.get_session(session["id"])["direction"] == "开发者验证工具"
    assert session["model"] == "test-model"
    assert model_client.generate_calls == 2


async def test_pipeline_repairs_one_invalid_editor_response():
    model_client = FakeModelClient(repair_editor=True)
    service = IdeaService(model_client)

    session = await service.generate_ideas("开发者验证工具", 3, "dev-tools")

    assert len(session["ideas"]) == 3
    assert model_client.generate_calls == 3


def test_session_delete_reports_missing_ids():
    session = IdeaService.create_session("方向", 3, "general")

    assert IdeaService.delete_session(session["id"]) is True
    assert IdeaService.delete_session(session["id"]) is False


async def test_generation_rejects_models_outside_configured_list():
    service = IdeaService(FakeModelClient())

    with pytest.raises(ValueError, match="所选模型不可用"):
        await service.generate_ideas("开发者验证工具", 3, "dev-tools", "hidden-model")

    assert IdeaService.sessions == {}
