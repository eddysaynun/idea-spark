from types import SimpleNamespace

from fastapi import FastAPI, Request

from routers.auth_router import _github_profile


class FetchResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    async def json(self):
        return self.payload


async def test_github_oauth_uses_worker_native_fetch():
    calls = []

    async def runtime_fetch(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("access_token"):
            return FetchResponse({"access_token": "short-lived-token"})
        return FetchResponse({"id": 7, "login": "octocat"})

    app = FastAPI()
    app.state.runtime_fetch = runtime_fetch
    request = Request({"type": "http", "app": app})

    profile = await _github_profile(request, "one-time-code", "client-id", "client-secret")

    assert profile["login"] == "octocat"
    assert calls[0][1]["method"] == "POST"
    assert calls[0][1]["body"] == "client_id=client-id&client_secret=client-secret&code=one-time-code"
    assert calls[1][1]["headers"]["Authorization"] == "Bearer short-lived-token"
