import pytest

import services.models.model_client as model_client_module
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

    async def text(self):
        if isinstance(self.data, str):
            return self.data
        return __import__("json").dumps(self.data)


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


@pytest.mark.asyncio
async def test_qwen35_requests_disable_thinking_for_structured_output():
    response = FakeResponse({"choices": [{"message": {"content": "[]"}}]})
    binding = FakeBinding(response)
    client = ModelClient(
        ModelConfig(base_url="https://qwen-api.example/v1", model="qwen35_27b"),
        service_binding=binding,
    )

    assert await client.generate("return json") == "[]"
    request_body = __import__("json").loads(binding.calls[0][1]["body"])
    assert request_body["chat_template_kwargs"] == {"enable_thinking": False}


@pytest.mark.asyncio
async def test_qwen35_can_enable_thinking_per_stage():
    response = FakeResponse({"choices": [{"message": {"content": "[]"}}]})
    binding = FakeBinding(response)
    client = ModelClient(
        ModelConfig(base_url="https://qwen-api.example/v1", model="qwen35_27b"),
        service_binding=binding,
    )

    await client.generate("criticize", thinking=True, max_tokens=32768)

    request_body = __import__("json").loads(binding.calls[0][1]["body"])
    assert request_body["chat_template_kwargs"] == {"enable_thinking": True}
    assert request_body["max_tokens"] == 32768


@pytest.mark.asyncio
async def test_local_fallback_uses_standard_library_transport(monkeypatch):
    calls = []

    async def fake_request(url, **options):
        calls.append((url, options))
        return 200, '{"choices":[{"message":{"content":"local result"}}]}'

    monkeypatch.setattr(model_client_module, "request_text", fake_request)
    client = ModelClient(ModelConfig(base_url="https://model.example/v1", api_key="local-key"))

    assert await client.generate("hello") == "local result"
    assert calls[0][0] == "https://model.example/v1/chat/completions"
    assert calls[0][1]["method"] == "POST"
    assert calls[0][1]["headers"]["Authorization"] == "Bearer local-key"


@pytest.mark.asyncio
async def test_stream_reports_reasoning_without_final_content():
    binding = FakeBinding(FakeResponse(
        'data: {"choices":[{"delta":{"reasoning_content":"分析"}}]}\n\n'
        'data: {"choices":[{"delta":{},"finish_reason":"length"}]}\n\n'
        'data: [DONE]\n'
    ))
    client = ModelClient(
        ModelConfig(base_url="https://qwen-api.example/v1", model="qwen35_27b"),
        service_binding=binding,
    )

    chunks = [chunk async for chunk in client.generate_stream("return json")]

    assert chunks[-1] == {
        "type": "error",
        "data": "模型未返回最终内容，可能是推理耗尽了输出预算",
    }
