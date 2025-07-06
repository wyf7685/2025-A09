# 开始运行

## 依赖

- 后端: [uv](https://github.com/astral-sh/uv)
  - 安装后在项目根目录执行 `uv sync`
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
DREMIO_BASE_URL=http://localhost:9047
DREMIO_USERNAME=username
DREMIO_PASSWORD=password
DREMIO_EXTERNAL_DIR=external
DREMIO_EXTERNAL_NAME=external

# LLM
TEST_MODEL_NAME=model-name
```

- Dremio 配置中的 `username` 和 `password` 为安装后首次登录时填写的用户名和密码
- LLM 中 `model-name` 填入测试使用的模型代号
- LangChain 配置指 `test_langchain.py` 的 main 函数中使用的具体 LLM 的配置
  - 参考代码对应部分选择合适的配置

## 说明

- 代码中的 `execute_mode` 参数
  - 在 docker 中执行 LLM 生成的代码
  - 需要使用 `docker build` 命令构建 runner 镜像，将镜像 ID 写入 .env 的 `DOCKER_RUNNER_IMAGE` 变量
  - 命令参考: `docker build . -f docker/Dockerfile.runner -t langchain-runner`

## TODO

- 删除 `src/` 下各目录中占位的 `.gitkeep`
