from app import load_model_config_from_env


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
