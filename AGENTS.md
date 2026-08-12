# Idea Spark Agent Instructions

本文件是所有编码 Agent 在本仓库的通用工作入口。

## 工作顺序（不得跳过）

1. 先执行 `git status --short`，保护已有改动。
2. 阅读需求涉及的完整调用链：UI → Context/API → Router → Service → Agent/ModelClient；修改共享函数前检索所有调用者。
3. 先写清验收条件和回归范围，再改代码。修根因，不在多个调用方重复打补丁。
4. 每个非平凡分支、解析器、模型编排或安全边界必须留下可运行测试。
5. 修改后先跑最小相关测试，再运行唯一完整门禁：`./scripts/check.sh`。
6. 只有门禁退出码为 0 才能声明完成；报告实际命令、通过数量、构建结果和未覆盖风险。

## 硬性边界

- 未经用户明确授权，不提交、推送、部署、删除用户数据或修改外部服务。
- 不在代码、日志、API 响应、测试夹具或文档中写入真实密钥。
- 前后端契约必须同一次修改并回归；禁止硬编码 `localhost` API 地址，浏览器统一使用 `/api`。
- 模型输出解析失败必须显式失败或有限重试，禁止用伪造 fallback 产物冒充成功。
- 市场数字、竞品结论和证据必须区分“已知事实 / 可观察信号 / 待验证假设”。没有检索来源时不得声称已验证。
- 不新增状态库、路由库、Agent 框架或测试框架，除非现有 React/FastAPI/pytest/Node test 无法满足且有可验证理由。
- 不以 lint、类型检查、单元测试或 build 中任意一项代替完整回归。

## 架构事实

- 前端：React + Vite；共享状态在 `frontend/src/context/AppContext.jsx`，SSE 解析在 `frontend/src/utils/sse.js`。
- 后端：FastAPI；路由只处理 HTTP 语义，业务会话在 `services/idea_service.py`，三阶段模型编排在 `services/agents/idea_pipeline.py`。
- 模型流程固定为 Explorer → Critic → Editor。扩展阶段时必须保留 JSON 校验、会话清理、SSE error 事件和单元测试。
- 配置响应永不返回密钥；空密钥表示保持原值。配置仅从环境变量初始化，运行时修改只存在进程内存；配置接口必须经过管理员令牌或本机访问校验。

## 完成报告格式

```text
改动：<用户可感知结果>
验证：<逐条命令及结果>
风险：<未覆盖项；没有则写“无已知风险”>
状态：未提交 / 未推送 / 未部署
```
