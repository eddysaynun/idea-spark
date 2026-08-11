#!/bin/bash

# Idea Spark - 一键启动脚本 (使用 uv)
# 同时启动前端和后端服务

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"

# 端口配置
BACKEND_PORT=3001
FRONTEND_PORT=3000

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║         🚀 Idea Spark - 一键启动脚本 (uv)         ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# 检查 uv
echo -e "${BLUE}🔍 检查 uv 环境...${NC}"
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}⚠️  未找到 uv，正在安装...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.local/bin/env 2>/dev/null || source ~/.cargo/env 2>/dev/null || true
fi
UV_VERSION=$(uv --version)
echo -e "${GREEN}✅ ${UV_VERSION}${NC}"

# 检查 Node.js
echo -e "${BLUE}🔍 检查 Node.js 环境...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ 未找到 Node.js，请先安装 Node.js 16+${NC}"
    exit 1
fi
NODE_VERSION=$(node --version)
echo -e "${GREEN}✅ Node.js ${NODE_VERSION}${NC}"

# 安装 Python 依赖
echo -e "${BLUE}📦 安装 Python 依赖...${NC}"
cd "${BACKEND_DIR}"
if [ -f "requirements.txt" ]; then
    echo -e "${YELLOW}⚠️  从 requirements.txt 安装依赖...${NC}"
    # 直接使用 uv pip install 到当前环境
    uv pip install -r requirements.txt --system
else
    echo -e "${RED}❌ 未找到 requirements.txt${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python 依赖就绪${NC}"
cd "${PROJECT_ROOT}"

# 检查前端依赖
echo -e "${BLUE}📦 检查前端依赖...${NC}"
if [ ! -d "${FRONTEND_DIR}/node_modules" ]; then
    echo -e "${YELLOW}⚠️  未找到前端依赖，正在安装...${NC}"
    cd "${FRONTEND_DIR}"
    npm install
    cd "${PROJECT_ROOT}"
fi
echo -e "${GREEN}✅ 前端依赖就绪${NC}"

# 检查端口占用
echo -e "${BLUE}🔍 检查端口占用...${NC}"
if lsof -i :${BACKEND_PORT} > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  端口 ${BACKEND_PORT} 已被占用，正在关闭...${NC}"
    lsof -ti:${BACKEND_PORT} | xargs kill -9 2>/dev/null || true
    sleep 1
fi

if lsof -i :${FRONTEND_PORT} > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  端口 ${FRONTEND_PORT} 已被占用，正在关闭...${NC}"
    lsof -ti:${FRONTEND_PORT} | xargs kill -9 2>/dev/null || true
    sleep 1
fi
echo -e "${GREEN}✅ 端口可用${NC}"

# 启动后端
echo ""
echo -e "${BLUE}🚀 启动后端服务 (Python FastAPI)...${NC}"
cd "${BACKEND_DIR}"
# 直接使用 python 运行（因为依赖已安装到系统环境）
python3 app.py &
BACKEND_PID=$!
cd "${PROJECT_ROOT}"

# 等待后端启动
sleep 3
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}❌ 后端启动失败${NC}"
    exit 1
fi
echo -e "${GREEN}✅ 后端已启动 (PID: ${BACKEND_PID})${NC}"

# 启动前端
echo ""
echo -e "${BLUE}🚀 启动前端服务 (React + Vite)...${NC}"
cd "${FRONTEND_DIR}"
npm run dev > /dev/null 2>&1 &
FRONTEND_PID=$!
cd "${PROJECT_ROOT}"

# 等待前端启动
sleep 3
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo -e "${RED}❌ 前端启动失败${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi
echo -e "${GREEN}✅ 前端已启动 (PID: ${FRONTEND_PID})${NC}"

# 显示启动信息
echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║                  🎉 启动成功！                        ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo -e "  ${GREEN}前端地址:${NC} http://localhost:${FRONTEND_PORT}"
echo -e "  ${GREEN}后端地址:${NC} http://localhost:${BACKEND_PORT}"
echo -e "  ${GREEN}API 文档:${NC} http://localhost:${BACKEND_PORT}/docs"
echo ""
echo -e "  ${YELLOW}进程 PID:${NC} 后端=${BACKEND_PID}, 前端=${FRONTEND_PID}"
echo ""
echo -e "  ${BLUE}按 Ctrl+C 停止所有服务${NC}"
echo ""

# 设置退出陷阱
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 正在停止服务...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    # 也关闭可能存在的 npm 子进程
    pkill -f "vite" 2>/dev/null || true
    pkill -f "python.*app.py" 2>/dev/null || true
    echo -e "${GREEN}✅ 服务已停止${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# 保持脚本运行
wait
