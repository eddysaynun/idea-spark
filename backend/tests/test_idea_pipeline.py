import json

from services.agents.idea_pipeline import IdeaPipeline


def idea(index):
    return {
        "name": f"Idea {index}", "tagline": "机会", "pain_point": "痛点", "solution": "方案",
        "target_user": "用户", "market_size": "待验证", "competitors": "替代品",
        "pricing": "待验证", "revenue": "待验证", "tech_stack": "Web", "advantage": "聚焦",
        "score": 8, "tags": ["MVP"], "evidence": ["访谈"],
        "assumptions": ["付费", "高频"], "risks": ["需求", "获客"], "confidence": "medium",
    }


class PipelineModel:
    def __init__(self):
        self.calls = []

    async def generate_stream(self, _prompt, _model=None, **options):
        self.calls.append(options)
        yield {"type": "content", "data": json.dumps([idea(index) for index in range(6)])}

    async def generate(self, _prompt, _model=None, **options):
        self.calls.append(options)
        if options["stage"] == "critic":
            return json.dumps([{"candidate_index": index} for index in range(6)])
        return json.dumps([idea(index) for index in range(3)])


async def test_pipeline_propagates_trace_and_returns_only_validated_ideas():
    model = PipelineModel()
    events = [event async for event in IdeaPipeline(
        model, "test-model", "project-1"
    ).run_events("验证方向", 3, "general")]

    assert len([event for event in events if event["type"] == "idea"]) == 3
    assert {call["trace_id"] for call in model.calls} == {"project-1"}
    assert {call["stage"] for call in model.calls} == {"explorer", "critic", "editor"}
    assert not {"text", "reasoning"}.intersection(event["type"] for event in events)
