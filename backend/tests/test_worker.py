import importlib
from types import SimpleNamespace

import pytest

class Headers(dict):
    def get(self, key, default=None):
        return super().get(key.lower(), default)


@pytest.mark.asyncio
async def test_generation_rate_limit_returns_retry_after_when_binding_rejects():
    rate_limit = importlib.import_module("services.rate_limit")
    limiter = SimpleNamespace(limit=lambda _options: None)

    async def reject(_options):
        return SimpleNamespace(success=False)

    limiter.limit = reject
    env = SimpleNamespace(GENERATION_RATE_LIMIT=limiter)
    request = SimpleNamespace(
        method="POST", url="https://idea.example/api/generate-stream",
        headers=Headers({"cookie": "idea_spark_session=opaque"}),
    )

    assert await rate_limit.rate_limit_retry_after(request, env) == 60
