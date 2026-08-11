# 🚀 Idea Spark - 启动指南

## 快速启动

### 方式一：一键启动脚本（推荐）

```bash
cd /Users/edward/workspace/edward/idea-spark
chmod +x start.sh
./start.sh
```

脚本会自动：
- ✅ 检查 Python 和 Node.js 环境
- ✅ 安装 uv（如果未安装）
- ✅ 安装 Python 依赖（使用 uv）
- ✅ 安装前端依赖（npm）
- ✅ 检查并释放端口占用
- ✅ 同时启动前后端服务
- ✅ 提供优雅的停止机制（Ctrl+C）

### 方式二：手动启动

#### 1. 启动后端（Python FastAPI）

```bash
cd backend

# 使用 uv 安装依赖
uv pip install -r requirements.txt --system

# 启动服务
uv run python app.py
```

后端运行在 http://localhost:3001

#### 2. 启动前端（React + Vite）

```bash
cd frontend

# 安装依赖（如果未安装）
npm install

# 启动开发服务器
npm run dev
```

前端运行在 http://localhost:3000

---

## 环境要求

- **Python**: 3.8+
- **Node.js**: 16+
- **uv**: 推荐（更快的 Python 包管理）

### 安装 uv（如果未安装）

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

---

## 访问地址

- **前端界面**: http://localhost:3000
- **后端 API**: http://localhost:3001
- **API 文档**: http://localhost:3001/docs

---

## 项目结构

```
idea-spark/
├── start.sh              # 一键启动脚本
├── backend/              # Python FastAPI 后端
│   ├── app.py           # 主应用
│   ├── agents.py        # Agent 框架
│   ├── model_client.py  # 模型调用
│   ├── requirements.txt # Python 依赖
│   └── config.json      # 配置（自动生成）
│
├── frontend/             # React 前端
│   ├── src/
│   │   ├── components/  # React 组件
│   │   ├── context/     # 全局状态
│   │   ├── api.js       # API 封装
│   │   └── App.jsx      # 主组件
│   ├── package.json
│   └── vite.config.js
│
└── README.md
```

---

## 使用流程

1. **启动服务**
   ```bash
   ./start.sh
   ```

2. **访问前端**
   打开浏览器访问 http://localhost:3000

3. **配置模型**（可选）
   - 点击"设置" Tab
   - 选择模型提供商（Hermes/OpenAI/Custom）
   - 填写对应的 URL 或 API Key
   - 点击"保存配置"

4. **生成 Ideas**
   - 点击"生成" Tab
   - 输入方向（如："AI Agent 工具"）
   - 选择数量和分类
   - 点击"生成 Ideas"

5. **查看详细方案**
   - 点击"详情" Tab
   - 点击任意 Idea 卡片
   - 查看完整技术方案

6. **查看历史**
   - 点击"历史" Tab
   - 查看所有生成记录

---

## 常见问题

### 1. 端口被占用

```bash
# 查看占用端口的进程
lsof -i :3001
lsof -i :3000

# 杀死进程
kill -9 <PID>
```

### 2. Python 依赖安装失败

```bash
# 使用 uv 安装
cd backend
uv pip install -r requirements.txt --system
```

### 3. 前端依赖安装失败

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### 4. 模型调用失败

- 确保 Hermes 或其他模型服务正在运行
- 检查配置中的 URL 是否正确
- 查看后端日志：`backend/app.py` 输出

---

## 停止服务

### 使用一键脚本启动时
直接按 `Ctrl+C` 即可优雅停止所有服务。

### 手动启动时

```bash
# 停止后端
# 在运行后端的终端按 Ctrl+C

# 停止前端
# 在运行前端的终端按 Ctrl+C
```

### 强制停止

```bash
# 杀死所有相关进程
pkill -f "python.*app.py"
pkill -f "vite"
pkill -f "npm run dev"
```

---

## 技术栈

### 后端
- **FastAPI** - 高性能异步 Python Web 框架
- **Uvicorn** - ASGI 服务器
- **Pydantic** - 数据验证
- **Aiohttp** - 异步 HTTP 客户端
- **Tenacity** - 重试机制

### 前端
- **React 18** - UI 库
- **Vite** - 构建工具
- **Axios** - HTTP 客户端
- **Lucide React** - 图标库

---

## 开发说明

### 添加新功能

1. **后端 API**
   - 在 `backend/app.py` 中添加新的路由
   - 使用 `@app.post()` 或 `@app.get()` 装饰器

2. **前端组件**
   - 在 `frontend/src/components/` 创建新组件
   - 在 `AgentView.jsx` 中导入和使用

3. **API 调用**
   - 在 `frontend/src/api.js` 中添加新的 API 方法
   - 在组件中使用 `await api.method()`

### 调试

- **后端日志**: 查看终端输出
- **前端调试**: 打开浏览器开发者工具
- **API 测试**: 访问 http://localhost:3001/docs

---

## 下一步优化

- [ ] 添加 WebSocket 实时进度推送
- [ ] 添加详情 Modal 展示
- [ ] 支持 Ideas 导出（JSON/Markdown）
- [ ] 添加用户认证
- [ ] 支持 Redis 会话存储
- [ ] 添加 Docker 部署
- [ ] 添加单元测试
- [ ] 添加 E2E 测试

---

## 许可证

MIT

---

**祝你使用愉快！** 🎉

如有问题，请查看项目 README.md 或联系作者。
