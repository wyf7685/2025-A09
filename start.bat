@echo off
title 数据分析Web应用启动器

echo 🚀 启动数据分析Web应用...
echo.

REM 检查Python环境
echo 📋 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python未安装，请先安装Python
    pause
    exit /b 1
)

REM 检查Node.js环境
echo 📋 检查Node.js环境...
node --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Node.js未安装，请先安装Node.js
    pause
    exit /b 1
)

REM 创建requirements.txt（如果不存在）
if not exist requirements.txt (
    echo 📝 创建requirements.txt...
    echo flask==2.3.3 > requirements.txt
    echo flask-cors==4.0.0 >> requirements.txt
    echo pandas==2.1.3 >> requirements.txt
    echo numpy==1.24.3 >> requirements.txt
    echo dremio-client==0.1.0 >> requirements.txt
    echo langchain==0.0.350 >> requirements.txt
    echo langchain-openai==0.0.2 >> requirements.txt
    echo python-dotenv==1.0.0 >> requirements.txt
)

REM 安装Python依赖
echo 📦 安装Python依赖...
pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ Python依赖安装失败
    pause
    exit /b 1
)

REM 安装前端依赖
echo 📦 安装前端依赖...
cd frontend
call npm install
if errorlevel 1 (
    echo ❌ 前端依赖安装失败
    pause
    exit /b 1
)
cd ..

REM 启动后端服务
echo 🔧 启动后端服务...
start "后端服务" cmd /k "python web_app.py"

REM 等待后端启动
timeout /t 3 /nobreak >nul

REM 启动前端开发服务器
echo 🎨 启动前端开发服务器...
cd frontend
start "前端服务" cmd /k "npm run dev"
cd ..

echo.
echo ✅ 应用启动完成!
echo 📍 前端地址: http://localhost:5173
echo 📍 后端地址: http://localhost:5000
echo.
echo 请在新打开的终端窗口中查看服务状态
echo 按任意键退出启动器...
pause >nul
