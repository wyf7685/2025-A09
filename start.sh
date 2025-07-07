#!/bin/bash

# Web应用启动脚本
echo "🚀 启动数据分析Web应用..."

# 检查Python环境
echo "📋 检查Python环境..."
if ! command -v python &> /dev/null; then
    echo "❌ Python未安装，请先安装Python"
    exit 1
fi

# 检查Node.js环境
echo "📋 检查Node.js环境..."
if ! command -v node &> /dev/null; then
    echo "❌ Node.js未安装，请先安装Node.js"
    exit 1
fi

# 安装Python依赖
echo "📦 安装Python依赖..."
pip install -r requirements.txt || {
    echo "❌ Python依赖安装失败"
    exit 1
}

# 安装前端依赖
echo "📦 安装前端依赖..."
cd frontend
npm install || {
    echo "❌ 前端依赖安装失败"
    exit 1
}
cd ..

# 启动后端服务
echo "🔧 启动后端服务..."
python web_app.py &
BACKEND_PID=$!
echo "后端服务PID: $BACKEND_PID"

# 等待后端启动
sleep 3

# 启动前端开发服务器
echo "🎨 启动前端开发服务器..."
cd frontend
npm run dev &
FRONTEND_PID=$!
echo "前端服务PID: $FRONTEND_PID"
cd ..

echo "✅ 应用启动完成!"
echo "📍 前端地址: http://localhost:5173"
echo "📍 后端地址: http://localhost:5000"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 设置信号处理
cleanup() {
    echo ""
    echo "🛑 正在停止服务..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    echo "✅ 所有服务已停止"
    exit 0
}

trap cleanup SIGINT SIGTERM

# 等待用户中断
wait
