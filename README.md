# 开始运行

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.13+-blue?logo=python&logoColor=edb641)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/vue-3.5+-42b883?logo=vuedotjs&logoColor=white)](https://vuejs.org/)

[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![basedpyright - checked](https://img.shields.io/badge/basedpyright-checked-42b983)](https://docs.basedpyright.com)
![works on my machine](https://img.shields.io/badge/works%20on-my%20machine-green)

> AI-powered data analysis platform with intelligent agents

## 依赖

- 后端: [uv](https://github.com/astral-sh/uv) + Docker (Desktop if on Windows)
  - 安装后在项目根目录执行 `uv sync`
  - 构建 CodeExecutor 所用的镜像: `docker build . -f docker/Dockerfile.executor -t $DOCKER_RUNNER_IMAGE`
  - 或者使用已构建的 CodeExecutor 镜像: `docker pull ghcr.io/wyf7685/2025-a09/executor:latest`
- [Dremio](https://www.dremio.com/):
  - 使用 docker
    - 安装后在项目根目录执行 `docker compose pull` 和 `docker compose up dremio -d --wait`
  - 单独部署
    - 参考 Dremio 文档安装
- 前端: [node.js](https://nodejs.org/) + [pnpm](https://pnpm.io/)
  - 在项目根目录执行 `pnpm i` 安装前端依赖 (vue3 + Element Plus)

## 配置

在项目根目录创建 `.env` 文件

```ini
# Dremio
DREMIO_BASE_URL=http://localhost:9047
DREMIO_REST_PORT=9047
DREMIO_FLIGHT_PORT=32010
DREMIO_USERNAME=username
DREMIO_PASSWORD=password
DREMIO_EXTERNAL_DIR=external
DREMIO_EXTERNAL_NAME=external

# 后端服务配置
HOST=0.0.0.0
PORT=8081

# 前端接口配置
VITE_API_BASE_URL=http://127.0.0.1:8081/api
```

## 启动调试

推荐使用 `VS Code` (或 `Cursor` 等) 侧边栏调试，一键启动前端+后端+Dremio容器

其他 IDE 请自行配置运行和调试

# 生产环境部署

- 复制 `docker/docker-compose.yml` 到服务器部署目录
- 使用 `docker compose pull` 拉取服务镜像
- 修改 `docker-compose.yml` 中的环境变量配置
- 执行 `docker compose up -d --wait` 启动服务
