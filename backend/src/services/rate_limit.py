"""Cloudflare-native public API rate-limit selection."""

import hashlib
from urllib.parse import urlparse


async def rate_limit_retry_after(request, env):
    if str(request.method).upper() != "POST":
        return None
    path = urlparse(str(request.url)).path
    if path in {"/api/auth/exchange", "/api/auth/restore"}:
        binding_name, group = "AUTH_RATE_LIMIT", "auth"
    elif path in {"/api/generate-stream", "/api/detail"}:
        binding_name, group = "GENERATION_RATE_LIMIT", "generation"
    elif path == "/api/billing/orders" or path == "/api/account/deletion" or path.startswith("/api/admin/"):
        binding_name, group = "SENSITIVE_RATE_LIMIT", "sensitive"
    else:
        return None
    limiter = getattr(env, binding_name, None)
    if limiter is None:
        return None
    cookie = request.headers.get("cookie", "")
    actor = cookie or request.headers.get("cf-connecting-ip", "anonymous")
    key = f"{group}:{hashlib.sha256(actor.encode()).hexdigest()}"
    result = await limiter.limit({"key": key})
    success = result.get("success") if isinstance(result, dict) else result.success
    return None if success else 60
