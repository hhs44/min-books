# services/agent-planner/Dockerfile
ARG SERVICE_NAME=agent-planner

FROM python:3.11-slim-bookworm AS base

ARG SERVICE_NAME

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 安装 uv
RUN pip install uv

# 复制 workspace 配置
COPY pyproject.toml uv.lock ./
COPY shared/ ./shared/
COPY services/${SERVICE_NAME}/ ./services/${SERVICE_NAME}/

# 安装依赖
RUN cd services/${SERVICE_NAME} && uv sync --frozen

# 复制其余代码
COPY services/${SERVICE_NAME}/app ./app

# 非 root 用户
RUN useradd -m -u 1000 minbook && chown -R minbook:minbook /app
USER minbook

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python -c "import os, httpx; httpx.get(f'http://localhost:{os.environ.get(\"SERVICE_PORT\", \"8000\")}/health').raise_for_status()" || exit 1

CMD ["sh", "-c", "uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port ${SERVICE_PORT:-8000}"]
