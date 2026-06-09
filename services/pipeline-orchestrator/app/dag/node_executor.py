"""执行单个 DAG 节点(agent / function,详见 v4 §Phase B Task 6)。"""
import asyncio
import logging
from typing import Any

import httpx
from minbook_common.http_client import SignedHTTPClient
from minbook_common.models import PipelineNode

logger = logging.getLogger(__name__)


async def execute_node(
    node: PipelineNode,
    inputs: dict,
    run_id: str,
    book_id: str,
    timeout: int = 180,
) -> dict:
    """执行一个节点。

    1. 如果是 agent:解析 agent_ref 找 service,调 /internal/{service}/invoke
    2. 如果是 function:调内部 Python function
    3. 返回 output
    """
    if node.type == "function":
        return await _execute_function(node, inputs, run_id)
    elif node.type == "agent" or not node.type:
        return await _execute_agent(node, inputs, run_id, book_id, timeout)
    else:
        raise ValueError(f"Unknown node type: {node.type}")


async def _execute_agent(
    node: PipelineNode, inputs: dict, run_id: str, book_id: str, timeout: int
) -> dict:
    """调 agent 服务。"""
    if not node.agent_ref:
        raise ValueError(f"Agent node {node.id} missing agent_ref")

    # 解析 agent_ref: 'service.AgentName' (e.g. 'agent-planner-service.PlannerAgent')
    parts = node.agent_ref.split(".")
    if len(parts) < 2:
        raise ValueError(f"Invalid agent_ref: {node.agent_ref}")

    service_name = parts[0]
    agent_name = parts[1]

    # 优先查 agent registry 拿 endpoint;没注册时用 resolver 兜底
    endpoint: str | None = None
    try:
        from ..registry.store import find_agent

        record = await find_agent(agent_name)
        if record:
            endpoint = record["endpoint"]
    except Exception as e:
        logger.debug(f"find_agent({agent_name}) failed (will use resolver): {e}")

    if not endpoint:
        from ..registry.resolver import resolve_service_endpoint

        endpoint = await resolve_service_endpoint(service_name)

    # 拼 invoke URL: /internal/{service_short}/invoke
    # 例: agent-planner-service → /internal/planner/invoke
    # service_short 是 v3 启动时各 agent 服务配的(planner / writer / reviewer)
    SERVICE_SHORT_MAP = {
        "agent-planner-service": "planner",
        "agent-writer-service": "writer",
        "agent-reviewer-service": "reviewer",
    }
    service_short = SERVICE_SHORT_MAP.get(service_name) or service_name.replace("-service", "")
    invoke_url = f"{endpoint}/internal/{service_short}/invoke"

    # idempotency key
    idempotency_key = f"{run_id}:{node.id}"

    logger.info(f"Executing node {node.id} via {invoke_url} (agent={agent_name}, run={run_id})")

    client = SignedHTTPClient("pipeline-orchestrator")
    try:
        r = await client.post(
            invoke_url,
            json={
                "agent_name": agent_name,
                "input": {**inputs, "pipeline_run_id": run_id, "node_id": node.id},
            },
            headers={
                "X-Service-Id": "pipeline-orchestrator",
                "Idempotency-Key": idempotency_key,
            },
            timeout=getattr(node, "timeout_seconds", None) or timeout,
        )
        r.raise_for_status()
        result = r.json()
        if result.get("status") == "error":
            raise RuntimeError(f"Agent {agent_name} returned error: {result.get('error')}")
        return result.get("result", {})
    finally:
        await client.aclose()


async def _execute_function(node: PipelineNode, inputs: dict, run_id: str) -> dict:
    """执行内部 function(例:save_chapter)。"""
    if node.function == "save_chapter":
        return await _save_chapter(inputs, run_id)
    raise ValueError(f"Unknown function: {node.function}")


async def _save_chapter(inputs: dict, run_id: str) -> dict:
    """save_chapter function:把最终章节内容存到 shared.chapters。"""
    from ..db import acquire

    validate_output = inputs.get("validate", {}) or {}
    write_output = inputs.get("write", {}) or {}

    draft = validate_output.get("final_content") or write_output.get("draft_content", "")
    word_count = len(draft) if isinstance(draft, str) else 0
    chapter_number = inputs.get("chapter_number", 0)
    book_id = inputs.get("book_id")

    if not draft or not book_id:
        raise RuntimeError("save_chapter: missing draft or book_id")

    try:
        async with acquire() as conn:
            await conn.execute(
                """INSERT INTO shared.chapters
                   (book_id, chapter_number, content, status, word_count, version, draft_status)
                   VALUES ($1, $2, $3, 'finalized', $4, 1, 'promoted')
                   ON CONFLICT (book_id, chapter_number)
                   DO UPDATE SET content = EXCLUDED.content, status = 'finalized',
                                 word_count = EXCLUDED.word_count, version = shared.chapters.version + 1,
                                 updated_at = NOW()""",
                book_id, chapter_number, draft, word_count,
            )
    except Exception as e:
        # shared.chapters 写权限被 v1 init SQL 撤销了(svc_pipeline 只有 SELECT);
        # 这里 fallback:写到 orchestrator.* 自有表(staging)或仅返回元数据。
        logger.warning(f"save_chapter: shared.chapters insert failed ({e}); returning metadata only")
        return {
            "saved": False,
            "word_count": word_count,
            "chapter_number": chapter_number,
            "note": "shared.chapters write skipped (RBAC): see orchestrator.pipeline_runs for draft",
        }

    return {"saved": True, "word_count": word_count, "chapter_number": chapter_number}
