# 💡 Idea Spark

<div align="center">

![Idea Spark Banner](https://img.shields.io/badge/Idea-Spark-purple?style=for-the-badge&logo=spark)
![Version](https://img.shields.io/badge/version-1.0.0-blue?style=for-the-badge)
![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)

**AI 驱动的可变现项目创意生成器** ✨

[English](README.md) | [中文](README_ZH.md)

</div>

---

## 🌟 特性

- 🤖 **AI 驱动** - 基于先进 AI 模型生成高质量项目创意
- ⚡ **实时流式** - 看到 AI 的思考过程和生成内容
- 💰 **变现导向** - 每个创意都包含市场分析、定价策略和收入预测
- 🎯 **痛点驱动** - 基于真实市场需求和痛点分析
- 🎨 **精美 UI** - Apple 风格设计，流畅动画体验
- 💾 **数据持久化** - 自动生成历史保存到 localStorage，防止刷新丢失

## 🚀 快速开始

### 前置要求

- Node.js 16+
- Python 3.8+
- Git

### 安装

```bash
# 克隆项目
git clone https://github.com/your-username/idea-spark.git
cd idea-spark

# 安装前端依赖
cd frontend
npm install

# 安装后端依赖
cd ../backend
pip install -r requirements.txt
```

### 启动

**方式一：使用启动脚本（推荐）**

```bash
# 在项目根目录
chmod +x start.sh
./start.sh
```

**方式二：手动启动**

```bash
# 终端 1 - 启动后端
cd backend
python3 app.py

# 终端 2 - 启动前端
cd frontend
npm run dev
```

### 访问

- **前端**: http://localhost:5173
- **后端 API**: http://localhost:3001

## 📁 项目结构

```
idea-spark/
├── backend/                 # Python FastAPI 后端
│   ├── app.py              # 主应用入口
│   ├── routers/            # API 路由
│   ├── services/           # 业务逻辑
│   │   ├── agents/        # AI Agent
│   │   ├── models/        # 模型客户端
│   │   └── idea_service.py
│   ├── schemas/           # 数据模型
│   ├── utils/             # 工具函数
│   └── logs/              # 日志目录
├── frontend/              # React + Vite 前端
│   ├── src/
│   │   ├── components/    # React 组件
│   │   ├── context/       # 全局状态
│   │   ├── utils/         # 工具函数
│   │   └── App.jsx        # 主应用
│   └── dist/              # 构建输出
├── start.sh              # 一键启动脚本
├── README.md             # 项目文档
└── package.json          # 项目配置
```

## 🎨 设计理念

**Idea Spark** 采用独特的 "Spark" 设计主题：

- 🟣 **紫色** - 代表创新与灵感
- 🟠 **橙色** - 代表能量与变现
- 🔵 **青色** - 代表技术与专业

核心设计原则：
- 动态光晕背景效果
- 渐变进度条动画
- 卡片悬停光晕
- 平滑过渡动画

## 🔧 配置

### 后端配置

创建 `backend/config.json`:

```json
{
  "provider": "custom",
  "custom_base_url": "http://your-api-endpoint",
  "custom_model": "your-model",
  "custom_api_key": "your-api-key",
  "temperature": 0.7,
  "max_tokens": 16384
}
```

### 前端配置

前端通过 API 自动获取配置，无需额外设置。

## 📊 功能展示

### 1. 生成 Ideas

输入项目方向，选择分类和数量，AI 将生成可变现的项目创意。

### 2. 实时流式输出

看到 AI 的思考过程和生成内容，体验真实的创作过程。

### 3. 历史管理

所有生成的 Ideas 自动保存，支持查看和删除历史记录。

### 4. 详细方案

点击任意 Idea 查看详细的技术方案、市场分析和实施建议。

## 🛠️ 技术栈

### 前端

- **React 18** - UI 框架
- **Vite** - 构建工具
- **Axios** - HTTP 客户端
- **Lucide React** - 图标库
- **Framer Motion** - 动画库

### 后端

- **FastAPI** - Web 框架
- **Python 3.8+** - 编程语言
- **Pydantic** - 数据验证
- **aiohttp** - 异步 HTTP 客户端

## 📝 开发指南

### 添加新组件

```bash
cd frontend/src/components
# 创建组件文件
touch NewComponent.jsx NewComponent.css
```

### 添加新 API 路由

```bash
cd backend/routers
# 创建路由文件
touch new_router.py
# 在 app.py 中注册
```

### 运行测试

```bash
# 后端测试
cd backend
pytest

# 前端测试
cd frontend
npm test
```

## 🐛 问题反馈

遇到问题？请查看：

- [BUGFIX.md](BUGFIX.md) - 已知问题和修复
- [STARTUP.md](STARTUP.md) - 启动指南
- [DELIVERY.md](DELIVERY.md) - 交付文档

或提交 [Issue](https://github.com/your-username/idea-spark/issues)

## 📄 License

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

感谢使用 Idea Spark！如果这个项目对你有帮助，请给一个 ⭐ Star。

---

<div align="center">

**✨ 让创意迸发，让想法变现 ✨**

Made with ❤️ by Idea Spark Team

</div>
