"""Small standard-library HTTP fallback for local development."""

import asyncio
from urllib.error import HTTPError
from urllib.request import Request, urlopen


async def request_text(url: str, *, method: str = "GET", headers=None, body=None, timeout: int = 20):
    """Return ``(status, text)`` without adding a production Worker dependency."""

    def execute():
        data = body.encode("utf-8") if isinstance(body, str) else body
        request = Request(url, data=data, headers=headers or {}, method=method)
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310 - caller controls trusted endpoints
                return response.status, response.read().decode("utf-8")
        except HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", errors="replace")

    return await asyncio.to_thread(execute)
