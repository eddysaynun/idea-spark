from types import SimpleNamespace

from app import load_model_config_from_bindings, load_model_config_from_env


def test_model_config_loads_supported_environment_values(monkeypatch):
    monkeypatch.setenv("IDEA_SPARK_MODEL_BASE_URL", "https://model.example/v1")
    monkeypatch.setenv("IDEA_SPARK_MODEL_NAME", "qwen3.5-27b")
    monkeypatch.setenv("IDEA_SPARK_MODEL_TEMPERATURE", "0.4")
    monkeypatch.setenv("IDEA_SPARK_MODEL_MAX_TOKENS", "8192")

    config = load_model_config_from_env()

    assert config.base_url == "https://model.example/v1"
    assert config.model == "qwen3.5-27b"
    assert config.temperature == 0.4
    assert config.max_tokens == 8192


def test_invalid_numeric_environment_values_fall_back_to_defaults(monkeypatch):
    monkeypatch.setenv("IDEA_SPARK_MODEL_TIMEOUT", "not-a-number")

    config = load_model_config_from_env()

    assert config.model == "gpt-4o-mini"
    assert config.timeout == 600


def test_model_config_loads_cloudflare_bindings_without_persistence():
    config = load_model_config_from_bindings(
        SimpleNamespace(
            IDEA_SPARK_MODEL_BASE_URL="https://worker-model.example/v1",
            IDEA_SPARK_MODEL_NAME="qwen3.5-27b",
            IDEA_SPARK_MODEL_API_KEY="secret",
            IDEA_SPARK_MODEL_TEMPERATURE="0.3",
            IDEA_SPARK_MODEL_MAX_TOKENS="4096",
        )
    )

    assert config.base_url == "https://worker-model.example/v1"
    assert config.model == "qwen3.5-27b"
    assert config.api_key == "secret"
    assert config.temperature == 0.3
    assert config.max_tokens == 4096
