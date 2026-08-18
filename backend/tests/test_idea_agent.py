import json

import pytest

from services.agents.idea_agent import DetailGenerationAgent, IdeaItem, IdeaOutputParser


def idea_payload(name="Signal Foundry"):
    return {
        "name": name,
        "tagline": "把模糊方向变成可验证机会",
        "pain_point": "独立开发者缺少市场证据",
        "solution": "结构化生成和比较机会",
        "target_user": "独立开发者",
        "market_size": "100 万潜在用户",
        "competitors": "通用对话工具",
        "pricing": "¥49/月",
        "revenue": "1000 用户可达 ¥49,000/月",
        "tech_stack": "React + FastAPI",
        "advantage": "证据导向",
        "score": 8.8,
        "tags": ["验证", "独立开发"],
    }


def test_parse_markdown_json_and_validate_count():
    agent = IdeaOutputParser()
    payload = [idea_payload(), idea_payload("Proof Map"), idea_payload("Niche Lens")]

    parsed = agent._parse_ideas_response(f"```json\n{json.dumps(payload)}\n```", 3)
    ideas = agent._validate_and_enrich(parsed, 3)

    assert [idea.name for idea in ideas] == ["Signal Foundry", "Proof Map", "Niche Lens"]


def test_invalid_model_output_is_not_disguised_as_success():
    agent = IdeaOutputParser()

    with pytest.raises(ValueError, match="不是有效"):
        agent._parse_ideas_response("not-json", 3)


def test_wrong_idea_count_is_rejected():
    agent = IdeaOutputParser()

    with pytest.raises(ValueError, match="预期 3"):
        agent._validate_and_enrich([idea_payload()], 3)


class ShortDetailModel:
    async def generate(self, _prompt, _model=None, **_options):
        return "内容过短"


async def test_detail_failure_does_not_return_fake_plan():
    agent = DetailGenerationAgent(ShortDetailModel())

    with pytest.raises(RuntimeError, match="生成失败"):
        await agent.generate_detail(IdeaItem(**idea_payload()))


class TracedDetailModel:
    def __init__(self):
        self.options = None

    async def generate(self, _prompt, _model=None, **options):
        self.options = options
        return "# 方案\n\n" + "可执行内容。" * 40


async def test_detail_generation_propagates_project_trace():
    model = TracedDetailModel()
    agent = DetailGenerationAgent(model, "selected-model", trace_id="project-detail")

    await agent.generate_detail(IdeaItem(**idea_payload()))

    assert model.options["trace_id"] == "project-detail"
    assert model.options["stage"] == "detail"
