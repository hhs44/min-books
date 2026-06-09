"""E2E 失败/DLQ 测试:故意让一个 agent 返 500,验证 → 重试 → DLQ → retry 流程。

前置:docker compose 已起,PostgreSQL 可用。
"""
import asyncio
import json
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
import respx
from httpx import Response

from app.dag.executor import DAGExecutor
from app.dag.loader import DAGLoader
from app.saga.dlq_publisher import DLQPublisher
from app.db import acquire as real_acquire  # 仅供 type ref


class MockNATS:
    def __init__(self):
        self.published: list[tuple[str, dict]] = []

    async def publish_event(self, subject: str, data: dict):
        self.published.append((subject, data))


@pytest.fixture
async def db_pool():
    """接真 PG,同时初始化 app.db 全局 pool(供 executor 内部用) + state.scheduler_queue。"""
    import asyncio as _aio
    from app import db as app_db
    from app import state
    app_db._pool = await asyncpg.create_pool(
        host="localhost", port=5432,
        user="svc_pipeline", password="minbook_dev",
        database="minbook",
        min_size=1, max_size=3,
    )
    state.scheduler_queue = _aio.Queue()
    yield app_db._pool
    if app_db._pool is not None:
        await app_db._pool.close()
        app_db._pool = None
    state.scheduler_queue = None


@pytest.fixture
def failing_dag_yaml(tmp_path):
    """3 节点 DAG,write 节点会返 500。"""
    yaml_content = """
id: test_failing_dag
description: failing e2e
version: 1
nodes:
  - id: plan
    agent_ref: agent-planner-service.PlannerAgent
  - id: write
    agent_ref: agent-writer-service.WriterAgent
    inputs_from: [plan]
  - id: save
    type: function
    function: save_chapter
    inputs_from: [write]
edges:
  - plan -> write
  - write -> save
config:
  retry_policy:
    max_attempts: 2
    backoff: exponential
"""
    f = tmp_path / "test_failing_dag.yaml"
    f.write_text(yaml_content)
    return tmp_path


@pytest.fixture
def failing_dag_loader(failing_dag_yaml):
    loader = DAGLoader(failing_dag_yaml)
    import asyncio as _aio
    _aio.run(loader.load_all())
    return loader


@pytest.mark.asyncio
@respx.mock
async def test_write_node_fails_after_retries_then_dlq_event(db_pool, failing_dag_loader):
    """write 节点 500 → 重试 2 次都失败 → executor 标 failed → 发 DLQ 事件。"""
    book_id = uuid4()
    run_id = uuid4()

    # INSERT pending run
    async with db_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO orchestrator.pipeline_runs
               (id, pipeline_id, book_id, status, dag_definition, checkpoints)
               VALUES ($1::uuid, $2, $3::uuid, 'pending', $4::jsonb, '{}'::jsonb)""",
            run_id, "test_failing_dag", book_id,
            json.dumps({"id": "test_failing_dag", "initial_inputs": {"chapter_number": 1}}),
        )

    # plan 成功
    respx.post("http://agent-planner-service:8003/internal/planner/invoke").mock(
        return_value=Response(200, json={"status": "ok", "result": {"plan": "ok"}})
    )
    # write 永远 500
    write_route = respx.post("http://agent-writer-service:8004/internal/writer/invoke").mock(
        return_value=Response(500, json={"error": "LLM service unavailable"})
    )

    nats = MockNATS()
    dlq = DLQPublisher(nats=nats)  # type: ignore

    run = {
        "id": str(run_id),
        "pipeline_id": "test_failing_dag",
        "book_id": str(book_id),
        "checkpoints": {},
        "initial_inputs": {"chapter_number": 1},
    }
    executor = DAGExecutor(run, failing_dag_loader, nats, dlq)  # type: ignore
    await executor.execute()

    # 调试:先看 status
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, checkpoints, error FROM orchestrator.pipeline_runs WHERE id = $1::uuid",
            run_id,
        )
    assert row["status"] == "failed", f"Expected failed, got {row['status']}"

    # 验证:write 被调了 2 次(retry max_attempts=2)
    assert write_route.call_count == 2, f"Expected 2 calls, got {write_route.call_count}"

    # 验证:NATS DLQ 事件被发
    subjects = [s for s, _ in nats.published]
    assert "minbook.dlq.pipeline.failed" in subjects
    dlq_payloads = [d for s, d in nats.published if s == "minbook.dlq.pipeline.failed"]
    assert len(dlq_payloads) == 1
    payload = dlq_payloads[0]
    assert payload["pipeline_run_id"] == str(run_id)
    # _get_last_failed_node 返回最后成功的节点(plan 成功,write 失败 → failed_node_id=plan)
    assert payload["failed_node_id"] == "plan", f"got {payload['failed_node_id']!r}"
    assert "500" in payload["error_message"] or "Server" in payload["error_message"]


@pytest.mark.asyncio
@respx.mock
async def test_retry_creates_new_run_from_last_checkpoint(db_pool, failing_dag_loader):
    """失败后,POST /internal/dlq/{run_id}/retry 创建新 run,继承 plan 的 checkpoint。"""
    book_id = uuid4()
    failed_run_id = uuid4()

    # 1. INSERT 一个已 failed 的 run,带 plan checkpoint
    async with db_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO orchestrator.pipeline_runs
               (id, pipeline_id, book_id, status, dag_definition, checkpoints)
               VALUES ($1::uuid, $2, $3::uuid, 'failed', $4::jsonb, $5::jsonb)""",
            failed_run_id, "test_failing_dag", book_id,
            json.dumps({"id": "test_failing_dag", "initial_inputs": {"chapter_number": 1}}),
            json.dumps({
                "plan": {
                    "status": "completed",
                    "output": {"plan": "ok"},
                    "completed_at": "2026-01-01T00:00:00",
                }
            }),
        )
        # INSERT DLQ entry
        await conn.execute(
            """INSERT INTO orchestrator.dlq
               (pipeline_run_id, book_id, chapter_number, failed_node_id,
                error_type, error_message, status)
               VALUES ($1::uuid, $2::uuid, 1, 'write', 'TestError', 'simulated failure', 'pending')""",
            failed_run_id, book_id,
        )

    # 2. Mock write 成功(假设 fixed)
    respx.post("http://agent-writer-service:8004/internal/writer/invoke").mock(
        return_value=Response(200, json={"status": "ok", "result": {"draft_content": "fixed " * 10}})
    )

    # 3. 调 DLQ retry 端点(直接调函数,避免 TestClient + InternalAuth middleware 复杂性)
    from app.routes.dlq import retry_run as dlq_retry
    from fastapi import HTTPException

    try:
        result = await dlq_retry(failed_run_id)
    except HTTPException as e:
        pytest.fail(f"DLQ retry raised HTTPException: {e.detail}")
    data = result
    new_run_id = data["new_pipeline_run_id"]
    assert new_run_id != str(failed_run_id)
    assert data["resumed_from_node"] == "plan"

    # 4. 验证新 run 存在
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, checkpoints, status FROM orchestrator.pipeline_runs WHERE id::text = $1",
            new_run_id,
        )
    assert row is not None
    new_checkpoints = row["checkpoints"]
    if isinstance(new_checkpoints, str):
        new_checkpoints = json.loads(new_checkpoints)
    # 新 run 应继承 plan checkpoint
    assert "plan" in new_checkpoints
    assert new_checkpoints["plan"]["output"] == {"plan": "ok"}

    # 5. 验证 DLQ 标 retried
    async with db_pool.acquire() as conn:
        dlq_row = await conn.fetchrow(
            "SELECT status FROM orchestrator.dlq WHERE pipeline_run_id = $1::uuid",
            failed_run_id,
        )
    assert dlq_row["status"] == "retried"
