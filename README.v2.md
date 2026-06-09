# MinBook v2 — Microservices Architecture

> ⚠️ 这是 v2 微服务架构的运维/开发 README。
> 旧 README.md / README.en.md / README.ja.md 是 v1 monorepo 时代的说明,与当前架构不再一致。
> v3 (agents + pipeline-orchestrator 业务) 完成后会合并。

v2 完成了 4 个核心基础设施服务(Gateway / LLM Gateway / State Service / Notification Service),
8 个容器协同运行(2 端口已预留 v3 业务)。

## 架构总览

```
                            ┌─────────────────┐
        ┌──────────────────►│     Gateway     │  8000  (对外 /api/*)
        │   client/browser  │  (FastAPI)      │
        │                   └─┬───────┬───────┘
        │                     │       │
        │                     │       │ /api/state/...   /api/llm/...
        │                     ▼       ▼
        │       ┌──────────┐  ┌──────────────┐  ┌────────────────────┐
        │       │  State   │  │  LLM Gateway │  │ Notification Svc   │
        │       │  Service │  │  (8006)      │  │ (8008)             │
        │       │  (8007)  │  └──────────────┘  └────────┬───────────┘
        │       └────┬─────┘                             │ NATS subscribe
        │            │                                   │ (JetStream)
        │            ▼                                   ▼
        │       ┌──────────────────────────────────────────────┐
        │       │  PostgreSQL   │  Redis  │  NATS (4222/8222)  │
        │       └──────────────────────────────────────────────┘
        │
        │  v3 业务(占位,端口已开):
        │    agent-planner 8003 / agent-writer 8004 / agent-reviewer 8005
        │    pipeline-orchestrator 8002
        └──────────────────────────────────────────────────
```

## 端口速查表

| 端口  | 服务                        | 范围  | 说明                       |
| ----- | --------------------------- | ----- | -------------------------- |
| 8000  | **gateway**                 | 外部  | 唯一对外的 API 入口        |
| 8002  | pipeline-orchestrator       | 外部  | v3 写作 pipeline(当前 404) |
| 8003  | agent-planner-service       | 外部  | v3 planner agent           |
| 8004  | agent-writer-service        | 外部  | v3 writer agent            |
| 8005  | agent-reviewer-service      | 外部  | v3 reviewer agent          |
| 8006  | **llm-gateway**             | 内部  | 3 LLM provider 代理        |
| 8007  | **state-service**           | 内部  | 7 真相文件 + 快照 + config |
| 8008  | **notification-service**    | 内部  | 4 通道 + NATS consumer     |
| 5432  | postgres                    | 内部  | minbook DB                 |
| 6379  | redis                       | 内部  | 限流 / 幂等性              |
| 4222  | nats (client)               | 内部  | 事件总线                   |
| 8222  | nats (monitoring HTTP)      | 内部  | `curl :8222/jsz` 看 stream |
| 3001  | grafana                     | 外部  | http://localhost:3001      |
| 3200  | tempo                       | 内部  | trace 后端                 |
| 4317  | otel-collector (gRPC)       | 内部  | OTLP 接收                  |
| 4318  | otel-collector (HTTP)       | 内部  | OTLP 接收                  |

**v2 完成范围(bold)**:gateway / llm-gateway / state-service / notification-service。
其余 4 服务是 v3 占位(skeleton 已起,但业务实现延后到 v3)。

## 启动

### 一次性准备

```bash
# 1. 复制 .env 模板(已用合理默认值,本地开发通常不需要改)
cp .env.example .env

# 2. 装依赖(uv workspace,会一次性装好 4 个 shared + 8 个 service)
make install
```

### 启动所有容器

```bash
make up
# 等价于:
#   docker compose -f infrastructure/docker-compose.yml up -d
#   sleep 5
#   make migrate   (跑 Alembic 初始化 shared.* / llm.* schema)
#   make ps
```

启动后:

- **第一次启动** gateway 会自动在 `~/.minbook/auth.token` 写一个 1 年有效的 JWT
- 容器日志里会打印该 token 的前 50 字符 — 可直接复制使用
- `curl http://127.0.0.1:8000/health` 应返 200

## 常用命令

```bash
make ps              # 看 14 容器状态
make logs            # tail -f 所有容器日志
make logs SVC=gateway  # 单容器日志(需先改 Makefile 支持 $SVC)

make test            # 跑所有 pytest(包括 v2 跨服务 e2e)
make lint            # ruff check
make typecheck       # mypy
make build           # 重建所有镜像(代码改了之后)
make down            # 停所有容器
make clean           # 清 __pycache__ / .pytest_cache / .ruff_cache / .mypy_cache
make migrate         # 重跑 Alembic(只改 schema 时)
```

## 验证(v2 集成)

```bash
# 33 项断言:8 服务 /health + 9 代理路由 + 4 容量 PUT/GET/409
bash scripts/verify-v2.sh

# 3 个跨服务 e2e pytest(需 unset 代理或用 env -u)
env -u ALL_PROXY -u HTTP_PROXY -u HTTPS_PROXY \
  uv run --package minbook-gateway pytest tests/test_e2e.py -v

# 7 步手动 e2e(看 v3 已知 defer 状态)
bash scripts/e2e-manual-phaseE.sh
```

## v2 范围 vs v3 待办

| 模块                   | v2 完成                          | v3 后续                 |
| ---------------------- | -------------------------------- | ----------------------- |
| gateway                | ✓ 9 路由 + auth + 限流 + i18n    | 接入前端 (v5 任务)      |
| llm-gateway            | ✓ 3 provider + 幂等 + 成本       | -                       |
| state-service          | ✓ 7 真相 + 快照 + config         | memory 代理(占位 501)   |
| notification-service   | ✓ 4 通道 + NATS consumer         | 模板引擎扩展            |
| pipeline-orchestrator  | skeleton (容器起)                | /internal/pipeline/* 业务 |
| agent-planner/writer/reviewer | skeleton (容器起)         | 业务 prompt + tool 调用 |
| 前端 (Studio)          | -                                | React + Vite(见 v5 plan) |

### v2 已知 defer(详见各 task 备注)

- `GET /api/books/<id>/memory` 返 404(gateway 暂无代理; state-service 内部返 501)
- `POST /api/books/<id>/write/next` 返 500(pipeline 内部 404, v3 修复路径)
- Alembic 迁移尚无正式 v2 版本(目前依赖手动 `make migrate` / 现有 schema)
- 8 业务 /health 中 agent-* / pipeline-orchestrator 是 skeleton 级 200,无业务接口

## 故障排查

### Bug 1:`/api/books/<id>/state/snapshots` 返 500
**已修复**(commit 61daa4f)。
原因为 gateway 把 `file_type=snapshots` 当成真相文件转发,触发 400。修复:在 `/{book_id}/state/{file_type}` 路由**之前**声明 `/{book_id}/state/snapshots` 显式路由。

### Bug 2:NATS consumer 报 `NotJSMessageError`
**已修复**(commit cea5782)。
原因为 `nc.subscribe()` 是 core NATS 订阅,handler 调 `msg.ack()` 抛 `nats.errors.NotJSMessageError`。
修复:`minbook_common/nats_client.py` 改用 `js.subscribe()` + durable consumer + `stream=minbook-events`(v2 spec §3.2.5)。
验证:`curl 127.0.0.1:8222/jsz?streams=true` 看到 `streams=1, consumers=2, pending=0` 表示 ack 正常。

### Token 找不到
`~/.minbook/auth.token` 由 gateway 首次启动自动生成。
如果丢失,重启 gateway:`make logs SVC=gateway` 然后 `make down && make up`。
或手动调 `init_local_token()` 重新签发。

### `/api/doctor` 报某个 service unhealthy
1. `make logs SVC=<unhealthy>` 看错误
2. 常见原因: postgres / nats 没起来 → `make ps` 看 health
3. 重建:`docker compose -f infrastructure/docker-compose.yml up -d --force-recreate <svc>`

## 文档

- v2 plan:`docs/superpowers/plans/2026-06-08-v2-core-services.md`
- v2 spec:`docs/superpowers/specs/2026-06-08-minbooks-mas-architecture-v2.md`
- v3 plan(后续):`docs/superpowers/plans/2026-06-08-v3-agents.md`(待写)

## v3 阶段(agents 完成)

v3 Phase A-D 完成 20 个 agent 模块 + 共享基础设施:

### Agent 清单(20 个)

| Service                | 端口 | Agent 数 | Agent                                                |
| ---------------------- | ---- | -------- | ---------------------------------------------------- |
| agent-planner-service  | 8003 | 4        | ArchitectAgent / PlannerAgent / ComposerAgent / FoundationReviewerAgent |
| agent-writer-service   | 8004 | 7        | WriterAgent / PolisherAgent / LengthNormalizer / ConsolidatorAgent / ChapterAnalyzerAgent / StyleAnalyzer / ShortFictionWriterAgent |
| agent-reviewer-service | 8005 | 9        | ContinuityAuditor / ReviserAgent / StateValidator / ObserverAgent / SettlerAgent / PostWriteValidator / AIGCDetector / SensitiveWordsDetector / RadarAgent |

### v3 集成验证

```bash
# 27 项断言:8 服务 /health + 20 agents + 42 单元测试 + 3 个 svc user 写测试
# + bug fix 1 (BaseAgent.to_card 警告消失) + bug fix 2 (密码认证失败消失)
bash scripts/verify-v3.sh

# 端到端 invoke 测试(每个 service 1 个 e2e — invoke → recall → LLM → store_episode → return)
# 需 unset 代理或用 env -u
for s in agent-planner agent-writer agent-reviewer; do
  cd services/$s && env -u ALL_PROXY uv run --package minbook-${s//-/_} pytest tests/test_invoke_e2e.py -v
done
```

### v3 关键修复(已 commit)

1. **BaseAgent.to_card 改为 classmethod**(commit 46afd05)
   - 原因:Python 3 没有 unbound method,`AgentClass.to_card(arg)` 把 `arg` 当 self
   - 修复:`@classmethod def to_card(cls, service, endpoint="")`
   - 影响:3 agent 服务注册 AgentCard 全部成功(警告消失)

2. **03-users.sql 密码统一**(commit dcf1523)
   - 原因:`PLACEHOLDER_PLANNER` 等占位密码与 MemoryClient fallback `'minbook_dev'` 不一致
   - 修复:所有 9 个 svc user 改为 `'minbook_dev'`(与 .env POSTGRES_PASSWORD 一致)
   - 生产:用户应自己用 `ALTER USER ... PASSWORD` 覆盖

### v3 已知 defer(等 v4 plan 处理)

- `pipeline-orchestrator /internal/orchestrator/agents/register` 返 404
  - 当前 3 agent 服务 register_all 走 try/except fallback(只 log,不 crash)
  - v4 plan 才补 orchestrator 路由
- `GET /api/books/<id>/write/next` 仍 500(同上 v2 defer,等 v4)
- Gateway `/api/agents/{name}/invoke` 路由 501 占位(v4 plan 接入 orchestrator)

### v3 单元测试覆盖(42 = 7 + 13 + 22)

| Service                | Tests | 覆盖                                                              |
| ---------------------- | ----- | ----------------------------------------------------------------- |
| agent-planner          | 7     | registry(2) + architect(1) + composer(2) + foundation_reviewer(2) |
| agent-writer           | 13    | registry(1) + writer(2) + polisher(3) + length_normalizer(2) + consolidator(3) + style_analyzer(2) |
| agent-reviewer         | 22    | registry(1) + continuity_auditor(3) + observer(2) + post_write_validator(3) + radar(2) + reviser(2) + settler(2) + state_validator(2) + aigc_sensitive(5) |

3 个 e2e invoke 测试(`tests/test_invoke_e2e.py`,per service)补充完整链路覆盖
(invoke → recall → LLM mock → store_episode → return),合计 45 测试。
