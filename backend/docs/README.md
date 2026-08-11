# Idea Spark 后端开发规范

## 📁 项目结构

```
backend/
├── app.py                 # FastAPI 应用入口
├── main.py                # 启动脚本（可选）
├── config.py              # 全局配置管理
├── docs/                  # 文档目录
│   ├── README.md         # 开发规范（本文档）
│   └── API.md            # API 文档
├── routers/               # 路由层（HTTP 接口定义）
│   ├── __init__.py
│   ├── config_router.py  # 配置相关路由
│   ├── ideas_router.py   # Ideas 生成路由
│   └── model_router.py   # 模型相关路由
├── services/              # 服务层（业务逻辑 + 具体实现）
│   ├── __init__.py
│   ├── idea_service.py   # Ideas 生成服务（编排层）
│   ├── detail_service.py # 详细方案服务（编排层）
│   ├── session_service.py # 会话管理服务（编排层）
│   ├── agents/           # Agent 实现（具体实现）
│   │   ├── __init__.py
│   │   ├── idea_agent.py
│   │   └── detail_agent.py
│   └── models/           # 模型客户端（具体实现）
│       ├── __init__.py
│       └── model_client.py
├── utils/                 # 工具层（通用工具函数）
│   ├── __init__.py
│   ├── logger.py         # 日志工具
│   ├── validator.py      # 数据验证工具
│   └── formatter.py      # 数据格式化工具
├── schemas/               # Pydantic 数据模型
│   ├── __init__.py
│   ├── config.py         # 配置 Schema
│   ├── ideas.py          # Ideas Schema
│   └── response.py       # 统一响应 Schema
├── tests/                 # 测试目录
│   ├── __init__.py
│   ├── test_routers.py
│   ├── test_services.py
│   └── test_agents.py
├── requirements.txt       # Python 依赖
├── pyproject.toml        # 项目配置
└── .env                  # 环境变量（不提交）
```

## 🎯 分层架构说明

### 1. Routers 层（路由层）
**职责**：HTTP 接口定义，请求参数验证，响应格式化

**规范**：
- 只定义 HTTP 接口，不包含业务逻辑
- 调用 Services 层处理业务
- 统一错误处理和响应格式
- 使用 Pydantic 进行请求/响应验证

**示例**：
```python
# routers/ideas_router.py
from fastapi import APIRouter, HTTPException
from schemas.ideas import GenerateRequest, GenerateResponse
from services.idea_service import IdeaService

router = APIRouter(prefix="/ideas", tags=["ideas"])

@router.post("/generate", response_model=GenerateResponse)
async def generate_ideas(request: GenerateRequest):
    try:
        result = await IdeaService.generate(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 2. Services 层（服务层）
**职责**：业务逻辑编排 + 具体实现

**结构**：
- **顶层文件** (`*_service.py`) - 业务编排层
  - 编排多个组件完成复杂业务
  - 管理业务状态和会话
  - 处理业务异常和错误恢复
  
- **子目录** (`agents/`, `models/`) - 具体实现层
  - 实现具体的业务逻辑
  - 封装第三方 API 调用
  - 实现核心算法和策略
  - 对上层提供清晰的接口

**规范**：
- 服务层同时包含编排和实现，便于模块化管理
- 编排层调用实现层，保持职责清晰
- 实现层对编排层提供稳定接口

**示例**：
```python
# services/idea_service.py (编排层)
from .agents.idea_agent import IdeaGenerationAgent
from .models.model_client import ModelClient

class IdeaService:
    @staticmethod
    async def generate(request) -> dict:
        # 编排 Agent 和 ModelClient
        client = ModelClient.get_instance()
        agent = IdeaGenerationAgent(client)
        
        ideas = await agent.generate_ideas(
            direction=request.direction,
            count=request.count,
            category=request.category
        )
        
        return {"ideas": ideas, "total": len(ideas)}

# services/agents/idea_agent.py (实现层)
class IdeaGenerationAgent:
    def __init__(self, model_client):
        self.client = model_client
    
    async def generate_ideas(self, direction, count, category):
        # 具体实现
        pass
```

### 3. Utils 层（工具层）
**职责**：通用工具函数，不依赖业务上下文

**规范**：
- 纯函数，无状态
- 可被任何层调用
- 提供通用功能（日志、格式化、验证等）

### 4. Schemas 层（数据模型）
**职责**：Pydantic 数据模型定义

**规范**：
- 定义所有请求/响应数据结构
- 使用 Pydantic 进行数据验证
- 保持与数据库模型分离

## 📝 开发规范

### 1. 命名规范

**文件命名**：
- 小写字母 + 下划线：`idea_service.py`
- 目录名：复数形式 `routers/`, `services/`

**类命名**：
- 大驼峰：`IdeaGenerationAgent`
- Service 类后缀：`IdeaService`
- Router 变量：`router = APIRouter()`

**函数命名**：
- 小写 + 下划线：`generate_ideas()`
- 动词开头：`get_`, `create_`, `update_`, `delete_`

**变量命名**：
- 小写 + 下划线：`model_config`
- 布尔值：`is_valid`, `has_error`

### 2. 代码规范

**导入顺序**：
```python
# 1. 标准库
import asyncio
import logging
from typing import List, Dict

# 2. 第三方库
from fastapi import APIRouter
from pydantic import BaseModel

# 3. 本地模块
from services.idea_service import IdeaService
from schemas.ideas import GenerateRequest
```

**日志使用**：
```python
logger = logging.getLogger(__name__)

logger.info("操作成功")
logger.warning("潜在问题")
logger.error("错误信息", exc_info=True)  # 包含堆栈
logger.debug("调试信息")
```

**错误处理**：
```python
try:
    result = await some_operation()
except ValueError as e:
    logger.error(f"参数错误：{e}")
    raise HTTPException(status_code=400, detail=str(e))
except Exception as e:
    logger.error(f"未知错误：{e}", exc_info=True)
    raise HTTPException(status_code=500, detail="内部错误")
```

### 3. API 设计规范

**URL 设计**：
- 使用名词，复数形式：`/api/ideas`
- RESTful 风格：`GET /ideas`, `POST /ideas`, `GET /ideas/{id}`
- 版本控制：`/api/v1/ideas`（预留）

**响应格式**：
```json
// 成功响应
{
  "success": true,
  "data": { ... },
  "message": "操作成功"
}

// 错误响应
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "错误描述"
  }
}
```

**状态码使用**：
- `200` - 成功
- `201` - 创建成功
- `400` - 请求参数错误
- `404` - 资源不存在
- `500` - 服务器内部错误

### 4. 测试规范

**单元测试**：
```python
# tests/test_services.py
import pytest
from services.idea_service import IdeaService

@pytest.mark.asyncio
async def test_generate_ideas():
    result = await IdeaService.generate({...})
    assert result["success"] is True
    assert len(result["ideas"]) > 0
```

**集成测试**：
```python
# tests/test_routers.py
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_generate_ideas_api():
    response = client.post("/api/generate", json={...})
    assert response.status_code == 200
```

### 5. 文档规范

**函数文档**：
```python
async def generate_ideas(direction: str, count: int) -> List[IdeaItem]:
    """
    生成项目 Ideas
    
    Args:
        direction: 项目方向描述
        count: 生成数量（5-20）
        
    Returns:
        Ideas 列表
        
    Raises:
        ValueError: 当参数无效时
        RuntimeError: 当模型调用失败时
    """
    pass
```

**模块文档**：
```python
"""
Ideas 生成服务模块

提供 Ideas 生成的业务逻辑编排，包括：
- 需求分析
- 模型调用
- 结果验证
- 会话管理
"""
```

## 🚀 开发流程

### 1. 新增功能

1. **设计 Schema** (`schemas/`)
2. **实现 Impl** (`impl/`)
3. **编排 Service** (`services/`)
4. **暴露 Router** (`routers/`)
5. **编写测试** (`tests/`)
6. **更新文档** (`docs/`)

### 2. 修改现有功能

1. **修改 Impl**（核心逻辑）
2. **更新 Service**（如需要）
3. **更新测试**
4. **验证兼容性**

### 3. 调试问题

1. **查看日志**（`logger.error` 带 `exc_info=True`）
2. **添加调试日志**（`logger.debug`）
3. **编写复现测试**
4. **修复并验证**

## 📦 依赖管理

**添加依赖**：
```bash
# 开发环境
pip install package_name
pip freeze > requirements.txt

# 或使用 uv
uv pip install package_name
uv pip freeze > requirements.txt
```

**安装依赖**：
```bash
pip install -r requirements.txt
# 或
uv pip install -r requirements.txt
```

## 🔧 本地开发

**启动开发服务器**：
```bash
cd backend
uvicorn app:app --reload --port 3001
```

**运行测试**：
```bash
pytest tests/ -v
```

**代码检查**：
```bash
# 格式化
black .
isort .

# 类型检查
mypy .

# lint
flake8 .
```

## 📚 最佳实践

1. **单一职责**：每个文件/类只负责一件事
2. **依赖注入**：避免硬编码依赖，便于测试
3. **异步优先**：IO 操作使用 async/await
4. **错误处理**：捕获具体异常，记录详细日志
5. **文档完整**：函数、类、模块都有文档字符串
6. **测试覆盖**：核心功能必须有单元测试
7. **代码复用**：通用功能提取到 utils
8. **版本控制**：大改动前创建分支

## 🐛 常见问题

**Q: 如何添加新的 API 端点？**
A: 在 `routers/` 创建新文件或添加路由，然后在 `app.py` 中注册。

**Q: 如何调试异步代码？**
A: 使用 `logger.debug()` 添加日志，或使用 `pytest-asyncio` 编写测试。

**Q: 如何处理数据库事务？**
A: 在 Service 层使用 `async with` 管理事务边界。

**Q: 如何添加新的模型提供商？**
A: 在 `impl/models/` 实现新的 ModelClient，遵循现有接口。

---

**最后更新**: 2024-08-11
**维护者**: Edward
