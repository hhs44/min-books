.PHONY: help install dev build test lint typecheck clean up down logs ps migrate

# 默认目标
help:
	@echo "MinBook 开发命令:"
	@echo "  make install     - 安装所有 Python 依赖(uv sync --all-packages)"
	@echo "  make dev         - 启动所有服务(docker-compose up)"
	@echo "  make down        - 停止所有服务"
	@echo "  make logs        - 查看所有服务日志"
	@echo "  make test        - 运行所有测试"
	@echo "  make typecheck   - 运行 mypy"
	@echo "  make lint        - 运行 ruff"
	@echo "  make clean       - 清理临时文件"
	@echo "  make migrate     - 跑 Alembic 迁移(创建 shared.* / llm.* schema)"

install:
	uv sync --all-packages

up:
	docker compose -f infrastructure/docker-compose.yml up -d
	@echo "等待服务启动..."
	@sleep 5
	@make migrate
	@make ps

down:
	docker compose -f infrastructure/docker-compose.yml down

logs:
	docker compose -f infrastructure/docker-compose.yml logs -f --tail=100

ps:
	docker compose -f infrastructure/docker-compose.yml ps

build:
	docker compose -f infrastructure/docker-compose.yml build

migrate:
	docker compose -f infrastructure/docker-compose.yml run --rm migrate

test:
	uv run --all-packages pytest

typecheck:
	uv run --all-packages mypy

lint:
	uv run --all-packages ruff check .

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
