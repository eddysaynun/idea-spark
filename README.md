<div align="center">

<img src="frontend/public/favicon.svg" width="88" alt="Idea Spark icon" />

# Idea Spark

**把模糊方向，变成可验证的产品机会。**

[`中文`](README.md) · [`English`](README_EN.md)

<sub>OPENAI-COMPATIBLE · MODEL-SELECTABLE · EVIDENCE-AWARE</sub>

<br /><br />

![Idea Spark](https://img.shields.io/badge/IDEA_SPARK-OPPORTUNITY_WORKBENCH-15131A?style=flat-square)
![Version](https://img.shields.io/badge/VERSION-2.0.0-6D4AFF?style=flat-square)
![License](https://img.shields.io/badge/LICENSE-MIT-2AAE8A?style=flat-square)

</div>

---

Idea Spark 是一个面向独立开发者与小团队的机会探索工作台：把模糊方向转成可比较的产品候选，并明确展示证据信号、关键假设、主要风险和置信度。

## 产品流程

后端不是一次性生成，而是三阶段模型流水线：

1. **Explorer** 生成双倍候选，主动扩大用户、场景、付费触发和交付形态的差异。
2. **Critic** 独立评估痛点、差异化、可执行性、变现与证据质量。
3. **Editor** 根据评审去重并定稿，输出严格结构化结果。

模型判断不等同于已验证市场事实。UI 会分别展示 `evidence`、`assumptions`、`risks` 与 `confidence`，提醒用户继续做访谈和外部核验。

## 技术栈

- Frontend：React 19、Vite 8、原生 Node test、oxlint
- Backend：FastAPI、Pydantic 2、aiohttp、pytest
- Model：用户自带 OpenAI-compatible endpoint，可在工作台按任务选择模型

## 本地启动

前置要求：Node.js、npm、Python 3.13+、[uv](https://docs.astral.sh/uv/)。

```bash
cd frontend
npm ci

cd ../backend
uv sync --group dev

cd ..
./start.sh
```

- Web：<http://localhost:3000>
- API：<http://localhost:3001>
- OpenAPI：<http://localhost:3001/docs>

`start.sh` 只启动并清理自己创建的两个进程，不会安装系统依赖、强制杀死占用端口的其他进程。

## 模型配置

在“模型设置”中填写 OpenAI-compatible `/v1` Base URL、API Key 和默认模型。检测接口返回模型列表后，用户可在工作台为每次机会探索选择模型。

模型配置不会写入文件或数据库。服务启动时从环境变量读取配置；设置页的修改只保存在当前后端进程内存中，重启即恢复启动配置。API 只返回 `has_*_api_key` 状态，不会把密钥原文传回浏览器。

公网部署必须设置 `IDEA_SPARK_ADMIN_TOKEN`。配置读取、修改和模型探测都要求请求头 `X-Admin-Token`；浏览器中的令牌只存在于设置页组件内存，刷新或离开页面即清除。未设置管理员令牌时，配置接口只允许本机访问。

常用启动变量：

```bash
IDEA_SPARK_ADMIN_TOKEN=<strong-random-token>
IDEA_SPARK_MODEL_BASE_URL=https://model.example/v1
IDEA_SPARK_MODEL_NAME=qwen3.5-27b
IDEA_SPARK_MODEL_API_KEY=<model-api-key>
IDEA_SPARK_MODEL_TEMPERATURE=0.7
IDEA_SPARK_MODEL_MAX_TOKENS=16384
IDEA_SPARK_MODEL_TIMEOUT=600
```

生产环境应通过平台 Secret/密钥管理器注入这些值，不要写进镜像或仓库。运行时只允许选择已配置的默认模型或 `/models` 探测到的模型，避免客户端传入任意模型名。

## Cloudflare 部署

仓库内置 Cloudflare Python Worker 配置，把 React 静态资产与 FastAPI `/api` 作为一个同源应用部署。`main` push 由 Cloudflare Workers Builds 自动构建并发布到 `idea-spark.heyedwardchen.com`。

- Root directory：`backend`
- Build command：`npm --prefix ../frontend ci && npm --prefix ../frontend run build`
- Deploy command：`uv run pywrangler deploy`
- Runtime secrets：`IDEA_SPARK_ADMIN_TOKEN`、模型 Base URL、模型名与 API Key

敏感值只配置在 Cloudflare Worker 的 Variables & Secrets 中；仓库与构建变量中不保存明文密钥。Python Workers 目前仍处于 Cloudflare open beta，生产使用前应持续关注运行时兼容性与限制。

## 质量门禁

所有改动交付前必须运行：

```bash
./scripts/check.sh
```

门禁依次执行：

- 前端 oxlint
- 前端 SSE 单元测试
- 前端 production build
- 后端 pytest
- Python compileall
- `git diff --check`

编码 Agent 的通用工作入口是 [`AGENTS.md`](AGENTS.md)。

## 目录

```text
frontend/src/
  components/               产品页面与组件
  context/AppContext.jsx    会话、生成与 API 状态
  utils/sse.js              支持跨 chunk 的 SSE 解析

backend/
  routers/                  HTTP/SSE 边界
  services/idea_service.py  会话与详情编排
  services/agents/
    idea_pipeline.py        Explorer → Critic → Editor
    idea_agent.py           输出解析与详情 Agent
  services/models/          模型提供商适配
  tests/                    后端回归测试
```

## 安全与数据边界

- 默认 CORS 仅允许本地前端来源，可通过 `CORS_ORIGINS` 配置。
- 模型配置不落盘；公网配置接口必须使用管理员令牌。
- 未完成的生成会话会在 pipeline 失败时清理。
- 无效或数量不符的模型 JSON 会显式失败，不使用伪造 fallback 结果冒充成功。
- 当前会话存储在单进程内存中，服务重启后清空；持久化数据库应在需要多实例或长期历史时再引入。
