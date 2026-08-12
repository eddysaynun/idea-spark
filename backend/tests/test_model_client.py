import pytest

from services.models.model_client import ModelClient, ModelConfig


def test_extracts_qwen_reasoning_from_delta():
    thinking, content = ModelClient._extract_stream_parts({
        "delta": {"reasoning_content": "先比较候选", "content": "最终结果"}
    })

    assert thinking == "先比较候选"
    assert content == "最终结果"


def test_extracts_legacy_reasoning_shape():
    thinking, content = ModelClient._extract_stream_parts({
        "reasoning_content": "分析", "content": "回答"
    })

    assert thinking == "分析"
    assert content == "回答"


def test_workbench_only_accepts_configured_or_detected_models():
    client = ModelClient(ModelConfig(model="default-model"))
    client._detected_models = ["model-a", "model-b"]

    assert client.validate_model("model-b") == "model-b"
    assert client.validate_model("") == "default-model"
    with pytest.raises(ValueError, match="所选模型不可用"):
        client.validate_model("hidden-model")


class FakeResponse:
    status = 200

    def __init__(self, data):
        self.data = data

    async def json(self):
        return self.data


class FakeBinding:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def fetch(self, url, **options):
        self.calls.append((url, options))
        return self.response


@pytest.mark.asyncio
async def test_detect_models_uses_service_binding_with_bearer_auth():
    binding = FakeBinding(FakeResponse({"data": [{"id": "qwen35_27b"}]}))
    client = ModelClient(
        ModelConfig(base_url="https://qwen-api.example/v1", api_key="secret"),
        service_binding=binding,
    )

    assert await client.detect_models() == ["qwen35_27b"]
    assert binding.calls == [
        (
            "https://qwen-api.example/v1/models",
            {"headers": {"Authorization": "Bearer secret"}},
        )
    ]


def test_parse_service_binding_sse_response():
    chunks = list(
        ModelClient._parse_sse_text(
            'data: {"choices":[{"delta":{"reasoning_content":"分析"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"答案"}}]}\n\n'
            'data: [DONE]\n'
        )
    )

    assert chunks == [
        {"type": "thinking", "data": "分析"},
        {"type": "content", "data": "答案"},
    ]
