<div align="center">

<img src="frontend/public/favicon.svg" width="88" alt="Idea Spark icon" />

# Idea Spark

**Turn a fuzzy direction into testable product opportunities.**

[`中文`](README.md) · [`English`](README_EN.md)

<sub>OPENAI-COMPATIBLE · MODEL-SELECTABLE · EVIDENCE-AWARE</sub>

<br /><br />

![Idea Spark](https://img.shields.io/badge/IDEA_SPARK-OPPORTUNITY_WORKBENCH-15131A?style=flat-square)
![Version](https://img.shields.io/badge/VERSION-2.0.0-6D4AFF?style=flat-square)
![License](https://img.shields.io/badge/LICENSE-MIT-2AAE8A?style=flat-square)

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
- Models: user-provided OpenAI-compatible endpoint with per-run model selection

## Local setup

Requirements: Node.js, npm, Python 3.8+, and [uv](https://docs.astral.sh/uv/).

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

Configure an OpenAI-compatible `/v1` Base URL, API key, and default model in Model Settings. After model discovery, users can choose a model for each workbench run.

Configuration is never written to a file or database. Startup values come from environment variables; UI changes live only in backend process memory and reset after restart.

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

## Quality gate

Run before delivery:

```bash
./scripts/check.sh
```

This runs frontend lint, Node tests, production build, backend pytest, Python compilation, and whitespace validation. General coding-agent instructions live in [`AGENTS.md`](AGENTS.md).

## Security and data boundaries

- CORS defaults to local frontend origins and can be set with `CORS_ORIGINS`.
- Model configuration is process-memory only; secrets are never returned by the API.
- Workbench requests may only select the configured default model or a model discovered from the endpoint.
- Invalid model JSON fails explicitly instead of returning fabricated fallback output.
- Sessions are stored in single-process memory and reset after restart.
