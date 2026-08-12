"""Cloudflare Python Worker production entrypoint."""

import os

from workers import WorkerEntrypoint

from app import app, initialize_application


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        import asgi

        os.environ["IDEA_SPARK_RUNTIME"] = "cloudflare"
        await initialize_application(app, self.env)
        return await asgi.fetch(app, request.js_object, self.env)
