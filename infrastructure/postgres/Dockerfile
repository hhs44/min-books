# infrastructure/postgres/Dockerfile
FROM postgres:16-bookworm

# 安装 pgvector(从 Debian 源)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*

COPY init/ /docker-entrypoint-initdb.d/

# 健康检查
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" || exit 1
