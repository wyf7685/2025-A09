# 开始运行

## 依赖

- 后端: [uv](https://github.com/astral-sh/uv) + Docker (Desktop if on Windows)
  - 安装后在项目根目录执行 `uv sync`
  - 构建 CodeExecutor 所用的镜像: `docker build . -f docker/Dockerfile.executor -t $DOCKER_RUNNER_IMAGE`
- [Dremio](https://www.dremio.com/):
  - 使用 docker
    - 安装后在项目根目录执行 `docker compose pull` 和 `docker compose up -d`
  - 单独部署
    - 参考 Dremio 文档安装
- 前端: [node.js](https://nodejs.org/) + [pnpm](https://pnpm.io/)
  - 在项目根目录执行 `pnpm i` 安装前端依赖 (vue3 + Element Plus)

## 配置

在项目根目录创建 `.env` 文件

```ini
# Dremio
DREMIO_BASE_URL=http://localhost
DREMIO_REST_PORT=9047
DREMIO_FLIGHT_PORT=32010
DREMIO_USERNAME=username
DREMIO_PASSWORD=password
DREMIO_EXTERNAL_DIR=external
DREMIO_EXTERNAL_NAME=external

# LLM
TEST_MODEL_NAME=xxx
# 可选: 根据调试使用的 API 自行配置
GOOGLE_API_KEY=xxx
OPENAI_API_KEY=xxx
OPENAI_API_BASE=xxx
OLLAMA_API_URL=xxx
```

## 启动调试

推荐使用 `VS Code` (或 `Cursor` 等) 侧边栏调试，一键启动前端+后端

其他 IDE 请自行配置运行和调试

## 说明

- 需要使用 `docker build` 命令构建 executor 镜像，将镜像 ID 写入 .env 的 `DOCKER_RUNNER_IMAGE` 变量
- 命令参考: `docker build . -f docker/Dockerfile.executor -t analyzer-executor`

# 生产环境部署

- 使用 `docker compose pull` 拉取 Dremio 等服务镜像
- 使用 `docker compose build` 构建前后端镜像
- 修改 `docker-compose.yml` 中的环境变量配置
- 执行 `docker compose up -d --wait` 启动服务
