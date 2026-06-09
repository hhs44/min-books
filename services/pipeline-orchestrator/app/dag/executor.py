"""DAG 执行器:调度节点、写 checkpoint、处理重试(详见 v4 §Phase B Task 5)。"""
import asyncio
import json
import logging
import random
import traceback
from datetime import datetime

import httpx
from minbook_common.nats_client import MinBookNATS

from ..db import acquire
from ..saga.cancellation import register_active_run, unregister_active_run
from ..saga.classifier import classify_error
from ..saga.dlq_publisher import DLQPublisher
from .loader import DAGLoader
from .node_executor import execute_node
from .topo import DAGAnalyzer

logger = logging.getLogger(__name__)


class DAGExecutor:
    """执行一个 Pipeline Run。

    用法:
        executor = DAGExecutor(run, dag_loader, nats, dlq_publisher)
        await executor.execute()
    """

    def __init__(
        self,
        run: dict,
        dag_loader: DAGLoader,
        nats: MinBookNATS,
        dlq_publisher: DLQPublisher,
    ):
        self.run = run
        self.run_id = str(run["id"])
        self.pipeline_id = run["pipeline_id"]
        self.dag = dag_loader.get(self.pipeline_id)
        if not self.dag:
            raise ValueError(f"DAG {self.pipeline_id} not found")
        self.analyzer = DAGAnalyzer(self.dag)
        self.dag_loader = dag_loader
        self.nats = nats
        self.dlq_publisher = dlq_publisher
        self.completed_nodes: set[str] = set(run.get("checkpoints", {}).keys())
        # 注:resumed runs 可能已带 checkpoints,会被 pre-populate
        self.cancellation_event = asyncio.Event()
        self.executed_groups: set[str] = set()  # 防止并行组重复跑

    async def execute(self):
        """主入口:从第一个节点开始,直到全部完成或失败。"""
        # 注册到 ACTIVE_RUNS(供 cancel_run 通知)
        register_active_run(self.run_id, self.cancellation_event)
        await self._mark_running()

        try:
            topo_order = self.analyzer.topological_order()
            for node_id in topo_order:
                if self.cancellation_event.is_set():
                    await self._mark_cancelled()
                    return

                if node_id in self.completed_nodes:
                    continue  # resumed run,skip already done

                node = self.analyzer.get_node(node_id)
                if not node:
                    logger.warning(f"Node {node_id} in edges but not in nodes; skipping")
                    self.completed_nodes.add(node_id)
                    continue

                # condition 不满足 → 跳过
                if node.condition and not await self._eval_condition(node.condition):
                    logger.info(f"Skipping node {node_id} (condition false: {node.condition})")
                    self.completed_nodes.add(node_id)
                    continue

                # 等待所有依赖完成
                await self._wait_for_deps(node_id)
                if self.cancellation_event.is_set():
                    await self._mark_cancelled()
                    return

                # 并行组:同 group 在主循环里只跑一次(由 executed_groups 去重)
                if node.parallel_group and node.parallel_group in self.executed_groups:
                    continue
                if node.parallel_group:
                    await self._execute_parallel_group(node.parallel_group)
                    self.executed_groups.add(node.parallel_group)
                else:
                    await self._execute_single_node(node)

            # 全部成功
            await self._mark_completed()
            logger.info(f"Pipeline run {self.run_id} completed")
        except asyncio.CancelledError:
            await self._mark_cancelled()
        except Exception as e:
            logger.exception(f"Pipeline run {self.run_id} failed: {e}")
            await self._mark_failed(e)
        finally:
            unregister_active_run(self.run_id)

    async def _wait_for_deps(self, node_id: str):
        """所有 incoming 节点必须 completed。"""
        incoming = self.analyzer._incoming(node_id)
        # 简单轮询(后续可改 event-based)
        for _ in range(6000):  # max 10 分钟
            if all(dep in self.completed_nodes for dep in incoming):
                return
            if self.cancellation_event.is_set():
                raise asyncio.CancelledError()
            await asyncio.sleep(0.1)
        raise TimeoutError(f"Timeout waiting for deps of {node_id}: {incoming}")

    async def _execute_single_node(self, node):
        result = await self._execute_with_retry(node)
        self.completed_nodes.add(node.id)
        await self._write_checkpoint(node.id, result)

    async def _execute_parallel_group(self, group_name: str):
        """并行执行同一 group 的所有节点。"""
        group_nodes = [n for n in self.dag.nodes if n.parallel_group == group_name]
        tasks = [self._execute_with_retry(node) for node in group_nodes]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for node, result in zip(group_nodes, results):
            if isinstance(result, Exception):
                # 一个失败 → 全组失败(raise 让顶层走 failed 路径)
                raise result
            self.completed_nodes.add(node.id)
            await self._write_checkpoint(node.id, result)

    async def _execute_with_retry(self, node) -> dict:
        """执行节点,带重试(详见 §11 §1 + §2)。"""
        max_attempts = self.dag.config.get("retry_policy", {}).get("max_attempts", 3)
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            if self.cancellation_event.is_set():
                raise asyncio.CancelledError()
            try:
                inputs = await self._collect_inputs(node)
                result = await execute_node(
                    node, inputs, self.run_id, str(self.run.get("book_id", "")),
                    timeout=180,
                )
                return result
            except Exception as e:
                profile = classify_error(e)
                last_error = e
                logger.warning(
                    f"Node {node.id} failed (attempt {attempt}/{max_attempts}, "
                    f"profile={profile.name}, retryable={profile.retryable}): {type(e).__name__}: {e}"
                )
                if not profile.retryable or attempt >= max_attempts:
                    raise
                # 退避(2^attempt + jitter)
                backoff_fn = profile.backoff_fn or (lambda a: 2 ** a)
                delay = backoff_fn(attempt)
                await asyncio.sleep(delay)
        # 不可达(循环一定 raise 或 return)
        if last_error:
            raise last_error
        raise RuntimeError("unreachable: retry loop exited without result")

    async def _collect_inputs(self, node) -> dict:
        """从 checkpoints + initial_inputs 收集节点的 inputs_from。"""
        inputs: dict = {"book_id": str(self.run.get("book_id", ""))}
        # run 里可能带 initial_inputs(从 scheduler_queue put 时塞进去)
        initial = self.run.get("initial_inputs") or {}
        for source in node.inputs_from:
            if source in self.completed_nodes:
                ckpt = self.run.get("checkpoints", {}).get(source, {})
                inputs[source] = ckpt.get("output")
            else:
                # 从 initial_inputs 拿(例如 book_settings, current_focus, truth_files)
                inputs[source] = initial.get(source)
        # 注入 chapter_number(常用)
        if "chapter_number" in initial and "chapter_number" not in inputs:
            inputs["chapter_number"] = initial["chapter_number"]
        return inputs

    async def _eval_condition(self, condition: str) -> bool:
        """简单的 condition 表达式求值(形如 'audit.has_critical_issues == true')。

        在受限 namespace 中 eval,只暴露 checkpoints + 简单字面量。
        """
        if not condition:
            return True
        try:
            audit_ckpt = self.run.get("checkpoints", {}).get("audit", {}).get("output", {})
            # 同时暴露 result 变量指向 audit(给形如 'result.has_critical_issues' 的写法)
            ns = {"audit": audit_ckpt, "result": audit_ckpt, "true": True, "false": False}
            return bool(eval(condition, {"__builtins__": {}}, ns))
        except Exception as e:
            logger.warning(f"Condition eval failed: {condition!r} → {e}; defaulting to False")
            return False

    async def _write_checkpoint(self, node_id: str, result: dict):
        """写 orchestrator.pipeline_runs.checkpoints(详见 §5.4)。"""
        ckpt_value = {
            "status": "completed",
            "output": result,
            "completed_at": datetime.utcnow().isoformat(),
        }
        try:
            async with acquire() as conn:
                await conn.execute(
                    """UPDATE orchestrator.pipeline_runs
                       SET checkpoints = COALESCE(checkpoints, '{}'::jsonb) || $1::jsonb
                       WHERE id = $2::uuid""",
                    json.dumps({node_id: ckpt_value}),
                    self.run_id,
                )
        except Exception as e:
            logger.warning(f"Failed to write checkpoint to DB for {node_id}: {e}")

        # 同步 in-memory(self.run['checkpoints'])
        if "checkpoints" not in self.run:
            self.run["checkpoints"] = {}
        self.run["checkpoints"][node_id] = ckpt_value

        # 发 NATS 事件
        try:
            await self.nats.publish_event(
                "minbook.pipeline.stage.completed",
                data={
                    "pipeline_run_id": self.run_id,
                    "node_id": node_id,
                    "duration_ms": 0,
                },
            )
        except Exception as e:
            logger.debug(f"Failed to publish stage.completed event: {e}")

    async def _mark_running(self):
        try:
            async with acquire() as conn:
                await conn.execute(
                    """UPDATE orchestrator.pipeline_runs
                       SET status = 'running', started_at = NOW()
                       WHERE id = $1::uuid AND status IN ('pending', 'cancelling')""",
                    self.run_id,
                )
        except Exception as e:
            logger.warning(f"Failed to mark run as running: {e}")

    async def _mark_completed(self):
        try:
            async with acquire() as conn:
                await conn.execute(
                    """UPDATE orchestrator.pipeline_runs
                       SET status = 'completed', completed_at = NOW()
                       WHERE id = $1::uuid""",
                    self.run_id,
                )
        except Exception as e:
            logger.warning(f"Failed to mark run as completed: {e}")

        try:
            await self.nats.publish_event(
                "minbook.pipeline.chapter.completed",
                data={
                    "pipeline_run_id": self.run_id,
                    "book_id": str(self.run.get("book_id", "")),
                    "node_outputs": {
                        nid: ckpt.get("output")
                        for nid, ckpt in self.run.get("checkpoints", {}).items()
                    },
                },
            )
        except Exception as e:
            logger.debug(f"Failed to publish chapter.completed: {e}")

    async def _mark_failed(self, error: Exception):
        try:
            async with acquire() as conn:
                await conn.execute(
                    """UPDATE orchestrator.pipeline_runs
                       SET status = 'failed', completed_at = NOW(),
                           error = $1::jsonb
                       WHERE id = $2::uuid""",
                    json.dumps({
                        "error_type": type(error).__name__,
                        "error_message": str(error),
                        "error_stack": traceback.format_exc(),
                    }),
                    self.run_id,
                )
        except Exception as e:
            logger.warning(f"Failed to mark run as failed in DB: {e}")

        # 入 DLQ
        try:
            await self.dlq_publisher.publish_pipeline_failed(
                pipeline_run_id=self.run_id,
                book_id=self.run.get("book_id"),
                failed_node_id=self._get_last_failed_node(),
                error=error,
                checkpoints=self.run.get("checkpoints", {}),
            )
        except Exception as e:
            logger.exception(f"Failed to publish pipeline to DLQ: {e}")

    async def _mark_cancelled(self):
        try:
            async with acquire() as conn:
                await conn.execute(
                    """UPDATE orchestrator.pipeline_runs
                       SET status = 'cancelled', completed_at = NOW()
                       WHERE id = $1::uuid""",
                    self.run_id,
                )
        except Exception as e:
            logger.warning(f"Failed to mark run as cancelled: {e}")

        try:
            await self.nats.publish_event(
                "minbook.pipeline.chapter.failed",
                data={
                    "pipeline_run_id": self.run_id,
                    "book_id": str(self.run.get("book_id", "")),
                    "reason": "user_cancelled",
                },
            )
        except Exception:
            pass

    def _get_last_failed_node(self) -> str:
        """找最后完成的前一个节点(作为 failed_node_id 的 best-guess)。"""
        completed = list(self.completed_nodes)
        return completed[-1] if completed else "unknown"
