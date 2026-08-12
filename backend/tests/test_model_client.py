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
