# 使用官方 Python 镜像作为基础
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装中文字体，修复matplotlib中文显示问题
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-wqy-microhei \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f -v

# 安装 uv
RUN pip install uv

# 复制依赖文件
COPY pyproject.toml uv.lock ./

# 使用 uv 来同步依赖
RUN uv pip sync pyproject.toml

# 复制所有项目文件到工作目录
COPY ./app ./app

# 暴露端口
EXPOSE 8000

# 运行应用的命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 