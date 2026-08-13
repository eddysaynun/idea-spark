<div align="center">

<img src="frontend/public/favicon.svg" width="88" alt="Idea Spark icon" />

# Idea Spark

**把模糊方向，变成可验证的产品机会。**

[`中文`](README.md) · [`English`](README_EN.md)

<sub>OPENAI-COMPATIBLE · MODEL-SELECTABLE · EVIDENCE-AWARE</sub>

<br /><br />

![Idea Spark](https://img.shields.io/badge/IDEA_SPARK-OPPORTUNITY_WORKBENCH-15131A?style=flat-square)
![Version](https://img.shields.io/badge/VERSION-2.0.0-6D4AFF?style=flat-square)
![License](https://img.shields.io/badge/LICENSE-PROPRIETARY-6D28D9?style=flat-square)

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
- Model：平台接入 OpenAI-compatible endpoint，登录用户可在工作台按任务选择已授权模型

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

由部署管理员通过 Secret 注入 OpenAI-compatible `/v1` Base URL、API Key 和默认模型。登录用户只能在工作台选择平台已授权的模型，无法读取或修改上游连接与密钥。

模型配置不会写入文件或数据库。服务启动时从环境变量或 Worker Secret 读取配置；受管理员令牌保护的运行时修改仅保存在当前实例内存中，重启即恢复启动配置。API 只返回密钥是否存在，不会把原文传回浏览器。

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
- Account secrets：`GITHUB_CLIENT_ID`、`GITHUB_CLIENT_SECRET`；启用托管多身份登录后再设置 `SUPABASE_URL`、`SUPABASE_ANON_KEY`
- D1：`idea-spark-production`（用户、会话、项目、方案与用量账本）

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

## 登录与管理

- GitHub OAuth 可独立使用；配置 Supabase 后支持任意有效邮箱注册、邮箱验证、密码登录，以及动态启用 GitHub、Google、Apple 身份。
- 邮箱注册支持填写 2–32 位用户名，作为账户显示名；第三方登录沿用已验证 Provider 返回的名称。
- 登录用户可在顶栏和“账户”页查看 Idea/详细方案的总额、已用、预占和剩余权益。在线支付接入前，额度包使用持久化购买申请并由管理员确认处理，不会自动扣款或伪造支付成功。
- 普通用户看不到管理入口。管理员直接访问 `/admin`，输入 `IDEA_SPARK_ADMIN_TOKEN` 后，可按邮箱、用户名或用户 ID 查询账户。
- 管理台可增加或扣减 Idea/详细方案额度、清理已确认异常的预占额度，并记录操作原因和前后值；管理员令牌只存在于当前页面内存中。
- 生产启用邮箱、GitHub 和 Google 登录；Apple 登录因需要付费 Apple Developer 账号暂不启用，入口不会展示。

## 商业权限与数据边界

- GitHub 或托管身份经服务端验证后签发 `HttpOnly + Secure + SameSite=Lax` 会话；数据库只保存 token 哈希。
- 免费额度由服务端 D1 账本判定，默认每个账户 5 个 Idea、2 个详细方案；客户端数字不参与授权。
- 生成接口要求幂等键并先占用额度，失败或中断会退回；已存在的详细方案直接读取且不重复扣额。
- 每个项目、历史和详细方案查询都同时包含 `user_id`，禁止跨用户读取与删除。
- 默认 CORS 仅允许本地前端来源，可通过 `CORS_ORIGINS` 配置。
- 模型配置不落盘；公网配置接口必须使用管理员令牌。
- 未完成的生成项目会标记失败并退回占用额度。
- 无效或数量不符的模型 JSON 会显式失败，不使用伪造 fallback 结果冒充成功。
- 历史记录持久化到 D1，并按认证用户隔离；登录后可显式导入旧版浏览器本地记录。

## License

Copyright © 2026 Edward. All rights reserved. 本仓库当前版本采用专有源码许可证，仅允许查看和评估；未经书面授权，不得复制、修改、部署、提供 SaaS 或商业使用。历史上已经按 MIT 发布的版本不受本次变更追溯影响。
