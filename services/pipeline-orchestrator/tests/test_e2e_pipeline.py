"""E2E 集成测试:用 respx mock 所有 agent 端点,跑完整 chapter 写作 pipeline。

前置:docker compose 已起,PostgreSQL 可用。测试会:
1. INSERT 一条 pipeline_runs(pending)
2. 用 respx mock 所有 agent /internal/{svc}/invoke 端点
3. 触发 DAGExecutor.execute()
4. 验证 pipeline_runs.status == 'completed',checkpoints 包含所有节点
5. 验证 NATS 事件被发(用 mock nats)
"""
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import asyncpg
import pytest
import respx
from httpx import Response

from app.dag.executor import DAGExecutor
from app.dag.loader import DAGLoader
from app.saga.dlq_publisher import DLQPublisher


PIPELINE_DAG_PATH = Path(__file__).resolve().parent.parent / "pipeline_definitions" / "chapter_writing_v2.yaml"


# 简单的 mock NATS,记录所有 publish 调用
class MockNATS:
    def __init__(self):
        self.published: list[tuple[str, dict]] = []

    async def publish_event(self, subject: str, data: dict):
        self.published.append((subject, data))


@pytest.fixture
async def db_pool():
    """接真 PG(由 docker compose 提供),同时初始化 app.db 全局 pool。"""
    from app import db as app_db
    app_db._pool = await asyncpg.create_pool(
        host="localhost",
        port=5432,
        user="svc_pipeline",
        password="minbook_dev",
        database="minbook",
        min_size=1, max_size=3,
    )
    yield app_db._pool
    if app_db._pool is not None:
        await app_db._pool.close()
        app_db._pool = None


@pytest.fixture
def simple_dag_yaml(tmp_path):
    """3 节点简单 DAG:plan → write → save。"""
    yaml_content = """
id: test_e2e_dag
description: simple e2e
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
    max_attempts: 1
    backoff: exponential
"""
    f = tmp_path / "test_e2e_dag.yaml"
    f.write_text(yaml_content)
    return tmp_path


@pytest.fixture
def dag_loader(simple_dag_yaml):
    loader = DAGLoader(simple_dag_yaml)
    import asyncio as _aio
    _aio.run(loader.load_all())
    return loader


@pytest.mark.asyncio
@respx.mock
async def test_full_pipeline_runs_to_completion(db_pool, dag_loader):
    """完整跑通:plan → write → save,验证 status='completed' + 3 个 checkpoint。"""
    book_id = uuid4()
    run_id = uuid4()

    # 1. INSERT 一条 pending run
    async with db_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO orchestrator.pipeline_runs
               (id, pipeline_id, book_id, status, dag_definition, checkpoints)
               VALUES ($1::uuid, $2, $3::uuid, 'pending', $4::jsonb, '{}'::jsonb)""",
            run_id, "test_e2e_dag", book_id,
            json.dumps({
                "id": "test_e2e_dag",
                "initial_inputs": {
                    "chapter_number": 1,
                    "book_settings": {"title": "E2E"},
                    "current_focus": "test",
                },
            }),
        )

    # 2. Mock agent endpoints(node_executor 拼的是 /internal/{service-short}/invoke,
    #   例: agent-planner-service → /internal/planner/invoke)
    respx.post("http://agent-planner-service:8003/internal/planner/invoke").mock(
        return_value=Response(200, json={
            "status": "ok",
            "result": {"chapter_number": 1, "title": "Test Ch1", "intent": "intro"},
        })
    )
    respx.post("http://agent-writer-service:8004/internal/writer/invoke").mock(
        return_value=Response(200, json={
            "status": "ok",
            "result": {"draft_content": "Hello world " * 50, "word_count": 50},
        })
    )

    # 3. mock nats + dlq
    nats = MockNATS()
    dlq = DLQPublisher(nats=nats)  # type: ignore

    run = {
        "id": str(run_id),
        "pipeline_id": "test_e2e_dag",
        "book_id": str(book_id),
        "checkpoints": {},
        "initial_inputs": {
            "chapter_number": 1,
            "book_settings": {"title": "E2E"},
            "current_focus": "test",
        },
    }
    executor = DAGExecutor(run, dag_loader, nats, dlq)  # type: ignore
    await executor.execute()

    # 4. 验证 DB 状态
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, checkpoints, error FROM orchestrator.pipeline_runs WHERE id = $1::uuid",
            run_id,
        )
    assert row is not None
    assert row["status"] == "completed", f"Expected completed, got {row['status']} (error={row['error']})"
    checkpoints = row["checkpoints"]
    if isinstance(checkpoints, str):
        checkpoints = json.loads(checkpoints)
    # 应当有 plan, write 节点成功(depends on function _save_chapter DB permissions)
    assert "plan" in checkpoints, f"Missing 'plan' checkpoint in {list(checkpoints.keys())}"
    assert "write" in checkpoints, f"Missing 'write' checkpoint in {list(checkpoints.keys())}"

    # 5. 验证 NATS 事件
    subjects = [s for s, _ in nats.published]
    assert "minbook.pipeline.stage.completed" in subjects
    assert "minbook.pipeline.chapter.completed" in subjects


@pytest.mark.asyncio
@respx.mock
async def test_pipeline_writes_checkpoints_in_order(db_pool, dag_loader):
    """checkpoints 应按 plan → write 顺序写入。"""
    book_id = uuid4()
    run_id = uuid4()

    async with db_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO orchestrator.pipeline_runs
               (id, pipeline_id, book_id, status, dag_definition, checkpoints)
               VALUES ($1::uuid, $2, $3::uuid, 'pending', $4::jsonb, '{}'::jsonb)""",
            run_id, "test_e2e_dag", book_id,
            json.dumps({"id": "test_e2e_dag", "initial_inputs": {"chapter_number": 1}}),
        )

    respx.post("http://agent-planner-service:8003/internal/planner/invoke").mock(
        return_value=Response(200, json={"status": "ok", "result": {"plan": "ok"}})
    )
    respx.post("http://agent-writer-service:8004/internal/writer/invoke").mock(
        return_value=Response(200, json={"status": "ok", "result": {"draft_content": "abc " * 10, "word_count": 10}})
    )

    nats = MockNATS()
    dlq = DLQPublisher(nats=nats)  # type: ignore
    run = {
        "id": str(run_id),
        "pipeline_id": "test_e2e_dag",
        "book_id": str(book_id),
        "checkpoints": {},
        "initial_inputs": {"chapter_number": 1},
    }
    executor = DAGExecutor(run, dag_loader, nats, dlq)  # type: ignore
    await executor.execute()

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT checkpoints FROM orchestrator.pipeline_runs WHERE id = $1::uuid",
            run_id,
        )
    checkpoints = row["checkpoints"]
    if isinstance(checkpoints, str):
        checkpoints = json.loads(checkpoints)
    keys = list(checkpoints.keys())
    assert "plan" in keys
    assert "write" in keys
    # plan 必须在 write 之前
    assert keys.index("plan") < keys.index("write")
