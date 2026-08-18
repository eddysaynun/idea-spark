# Idea Spark Backend

## 分层

- `app.py`：应用生命周期、CORS、路由注册和模型客户端关闭。
- `routers/`：HTTP/SSE 参数、状态码和安全响应，不放业务编排。
- `services/account_store.py`：D1 用户、额度、项目、详情和支付持久化。
- `services/agents/idea_pipeline.py`：Explorer → Critic → Editor 三阶段生成。
- `services/agents/idea_agent.py`：严格 JSON 输出解析和详细方案 Agent。
- `services/models/model_client.py`：部署方 OpenAI-compatible 服务适配与授权模型选择。
- `tests/`：解析、pipeline、会话、密钥边界和 Qwen reasoning 字段回归。

## 生成流程

`POST /api/generate-stream` 创建项目，并通过 SSE 依次发送：

```text
start
progress: 机会探索
progress: 批判评估
progress: 结构化定稿
idea × N
progress: 完成
complete
```

任一阶段失败时，未完成项目会被删除、额度会退还并发送 `error`。结构无效时允许一次只修 JSON 的受控修复；第二次仍无效则显式失败，绝不生成备用业务数据。

最终 Idea 字段除产品信息外，还包括：

- `evidence`：可观察信号或验证路径
- `assumptions`：尚未验证的关键假设
- `risks`：主要失败风险
- `confidence`：`low | medium | high`

## API

| Method | Path | 说明 |
|---|---|---|
| GET | `/health` | 健康检查 |
| GET | `/api/models` | 返回登录用户可选择的部署授权模型名，不暴露连接或密钥 |
| POST | `/api/generate` | 非流式三阶段生成 |
| POST | `/api/generate-stream` | SSE 三阶段生成 |
| POST | `/api/detail` | 生成并缓存详细方案 |
| GET | `/api/sessions` | 会话列表 |
| GET/DELETE | `/api/sessions/{id}` | 会话详情/删除 |
| GET | `/api/account/export` | 导出当前账号全部业务数据 |
| POST | `/api/account/deletion` | 申请 7 天可恢复注销并立即结束会话 |
| POST | `/api/auth/restore` | 在冷静期内重新验证并恢复账号 |
| POST | `/api/billing/orders` | 创建支付宝额度订单 |
| POST | `/api/admin/payment-orders/{id}/query` | 管理员主动查单并幂等到账 |
| POST | `/api/admin/payment-orders/{id}/refund` | 对未消费额度执行整单原路退款 |
| POST | `/api/product-events` | 记录白名单内的最小产品行为事件 |

## 开发与回归

```bash
uv sync --group dev
uv run pytest -q
uv run python -m compileall -q .
```

仓库级完整门禁仍以根目录 `./scripts/check.sh` 为准。

## 当前边界

- 用户、额度、项目和详情使用 D1 持久化并按当前用户隔离。
- 身份统一由 Supabase 验证；服务端应用会话只保存 token 哈希。账号到期删除需要 Worker Secret `SUPABASE_SECRET_KEY`。
- Cloudflare 原生绑定分别限制登录交换、公开生成和敏感写操作；注册 Turnstile Secret 仅配置在 Supabase，浏览器只接收 Site Key。
- 支付宝 RSA2 私钥只存在于独立 Payment Gateway Worker；主应用通过 Service Binding 使用查单、验签和退款能力。
- 常规测试使用 fake model，不访问真实外部服务。
- 真实外部模型冒烟测试会传输用户输入，必须在明确授权后执行。
