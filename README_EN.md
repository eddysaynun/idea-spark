<div align="center">

<img src="frontend/public/favicon.svg" width="88" alt="Idea Spark icon" />

# Idea Spark

**Turn a fuzzy direction into testable product opportunities.**

[`中文`](README.md) · [`English`](README_EN.md)

<sub>OPENAI-COMPATIBLE · MODEL-SELECTABLE · EVIDENCE-AWARE</sub>

<br /><br />

![Idea Spark](https://img.shields.io/badge/IDEA_SPARK-OPPORTUNITY_WORKBENCH-15131A?style=flat-square)
![Version](https://img.shields.io/badge/VERSION-2.0.0-6D4AFF?style=flat-square)
![License](https://img.shields.io/badge/LICENSE-PROPRIETARY-6D28D9?style=flat-square)

</div>

---

Idea Spark is an opportunity exploration workbench for independent developers and small teams. It turns an initial direction into comparable product candidates with explicit evidence signals, assumptions, risks, and confidence.

## How it works

The backend uses a three-stage model workflow:

1. **Explorer** creates a broad candidate set across users, contexts, buying triggers, and delivery forms.
2. **Critic** reviews pain, differentiation, feasibility, monetization, and evidence quality.
3. **Editor** removes duplicates and produces strictly structured final opportunities.

Model judgments are not verified market facts. The UI separates `evidence`, `assumptions`, `risks`, and `confidence` so users know what still requires interviews or external validation.

## Stack

- Frontend: React 19, Vite 8, Node test, oxlint
- Backend: FastAPI, Pydantic 2, aiohttp, pytest
- Models: platform-managed OpenAI-compatible endpoint with per-run selection from authorized models

## Local setup

Requirements: Node.js, npm, Python 3.13+, and [uv](https://docs.astral.sh/uv/).

```bash
cd frontend
npm ci

cd ../backend
uv sync --group dev

cd ..
./start.sh
```

- Web: <http://localhost:3000>
- API: <http://localhost:3001>
- OpenAPI: <http://localhost:3001/docs>

## Model connection

Deployment administrators inject the OpenAI-compatible `/v1` Base URL, API key, and default model as secrets. Signed-in users may choose only from models authorized by the platform and cannot read or change upstream credentials.

Configuration is never written to a file or database. Startup values come from environment variables or Worker secrets; admin-token-protected runtime changes live only in process memory and reset after restart.

```bash
IDEA_SPARK_ADMIN_TOKEN=<strong-random-token>
IDEA_SPARK_MODEL_BASE_URL=https://model.example/v1
IDEA_SPARK_MODEL_NAME=qwen3.5-27b
IDEA_SPARK_MODEL_API_KEY=<model-api-key>
IDEA_SPARK_MODEL_TEMPERATURE=0.7
IDEA_SPARK_MODEL_MAX_TOKENS=16384
IDEA_SPARK_MODEL_TIMEOUT=600
```

Public deployments must set `IDEA_SPARK_ADMIN_TOKEN`. Configuration reads, updates, and remote model discovery require `X-Admin-Token`; without a token those endpoints only accept local requests.

## Cloudflare deployment

The repository includes a Cloudflare Python Worker configuration that serves the React assets and FastAPI `/api` as one same-origin application. Cloudflare Workers Builds deploys every `main` push to `idea-spark.heyedwardchen.com`.

- Root directory: `backend`
- Build command: `npm --prefix ../frontend ci && npm --prefix ../frontend run build`
- Deploy command: `uv run pywrangler deploy`
- Runtime secrets: admin token, model Base URL, model name, and API key
- Account secrets: `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET`
- D1: `idea-spark-production` for users, sessions, projects, plans, and usage events

Keep secret values in Cloudflare Worker Variables & Secrets, never in the repository or build variables. Cloudflare Python Workers are currently in open beta, so production use should continue to track runtime compatibility and limits.

## Quality gate

Run before delivery:

```bash
./scripts/check.sh
```

This runs frontend lint, Node tests, production build, backend pytest, Python compilation, and whitespace validation. General coding-agent instructions live in [`AGENTS.md`](AGENTS.md).

## Commercial access and data boundaries

- GitHub OAuth issues an `HttpOnly`, `Secure`, `SameSite=Lax` server-side session; only its hash is stored.
- Server-side D1 usage accounting grants 5 ideas and 2 detailed plans per account by default. Client counters are never trusted for authorization.
- Generation requires idempotency keys, reserves usage before model work, and refunds failed or interrupted work. Cached detailed plans do not charge twice.
- Every project, history, and plan query is scoped by authenticated `user_id`.
- CORS defaults to local frontend origins and can be set with `CORS_ORIGINS`.
- Model configuration is process-memory only; secrets are never returned by the API.
- Workbench requests may only select the configured default model or a model discovered from the endpoint.
- Invalid model JSON fails explicitly instead of returning fabricated fallback output.
- History is persisted in D1 and isolated per authenticated user. Users may explicitly import legacy browser-local sessions.

## Authentication and administration

- GitHub OAuth works independently. When Supabase is configured, any valid email can register and verify an account, while GitHub, Google, and Apple providers can be enabled individually.
- Email registration accepts a 2–32 character display name. Signed-in users can inspect total, used, reserved, and remaining Idea and detailed-plan credits from the account page.
- Until online payments are integrated, credit packages create a persistent purchase request for manual review; the product never presents that request as a completed payment.
- The administration page is hidden from regular navigation. Visit `/admin` directly and authenticate with `IDEA_SPARK_ADMIN_TOKEN` to search users, adjust Idea or detailed-plan limits, repair confirmed stuck reservations, and review the audit history.
- Production enables email, GitHub, and Google login. Apple login remains disabled because it requires a paid Apple Developer account, so no unavailable action is shown.

## License

Copyright © 2026 Edward. All rights reserved. The current source is viewable for evaluation only and may not be copied, modified, deployed, offered as SaaS, or used commercially without written permission. Versions previously released under MIT remain governed by their original license.
