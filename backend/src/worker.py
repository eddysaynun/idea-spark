"""Cloudflare Python Worker production entrypoint."""

import os

from workers import Response, WorkerEntrypoint, fetch

os.environ["IDEA_SPARK_RUNTIME"] = "cloudflare"

from app import app, initialize_application

app.state.runtime_fetch = fetch


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        import asgi
        from services.rate_limit import rate_limit_retry_after

        retry_after = await rate_limit_retry_after(request, self.env)
        if retry_after:
            return Response(
                '{"detail":"请求过于频繁，请稍后重试"}', status=429,
                headers={"Content-Type": "application/json", "Retry-After": str(retry_after)},
            )

        await initialize_application(app, self.env)
        return await asgi.fetch(app, request.js_object, self.env)

    async def scheduled(self, controller, env, ctx):
        from routers.account_router import delete_supabase_identity
        from services.payment_reconciliation import reconcile_payments

        await initialize_application(app, self.env)

        async def delete_identity(subject):
            await delete_supabase_identity(app.state, subject)

        await reconcile_payments(app.state.account_store, app.state.payment_registry)
        await app.state.account_store.process_due_deletions(delete_identity)
