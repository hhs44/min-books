"""Pipeline Orchestrator:DAG 引擎 + Agent Registry + 端到端调度(详见 v4 plan)。

Phase A-C 范围:服务骨架 + DAG 引擎 + 错误分类 + DLQ + 取消协议。
HTTP 路由见 Phase D。
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from minbook_common.middleware import InternalAuthMiddleware
from minbook_common.nats_client import MinBookNATS
from minbook_otel.logging import setup_logging
from minbook_otel.tracing import init_tracing, instrument_fastapi

from .config import get_settings
from .cron.dlq_syncer import DLQSyncer
from .cron.stale_scanner import StaleScanner
from .dag.loader import DAGLoader
from .db import close_db, init_db
from .registry.heartbeat import HeartbeatMonitor
from .saga.dlq_publisher import DLQPublisher

settings = get_settings()
setup_logging(level=os.environ.get("LOG_LEVEL", "INFO"))
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
init_tracing(settings.service_name, settings.service_version)
logger = logging.getLogger(__name__)

# 全局共享资源
dag_loader: DAGLoader | None = None
nats: MinBookNATS | None = None
heartbeat_monitor: HeartbeatMonitor | None = None
dlq_publisher: DLQPublisher | None = None
stale_scanner: StaleScanner | None = None
dlq_syncer: DLQSyncer | None = None
scheduler_queue: asyncio.Queue | None = None
_background_tasks: list[asyncio.Task] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global dag_loader, nats, heartbeat_monitor, dlq_publisher, stale_scanner, dlq_syncer, scheduler_queue, _background_tasks

    logger.info(f"[startup] {settings.service_name} v{settings.service_version}")

    # 1. init DB
    try:
        await init_db()
        logger.info("[startup] DB pool initialized")
    except Exception as e:
        logger.exception(f"[startup] DB init failed (continuing without DB): {e}")

    # 2. load DAGs
    dag_loader = DAGLoader(definitions_dir=settings.dag_definitions_dir)
    try:
        await dag_loader.load_all()
        logger.info(f"[startup] DAGs loaded: {dag_loader.list_ids()}")
    except Exception as e:
        logger.exception(f"[startup] DAG loading failed: {e}")

    # 3. NATS
    try:
        nats = MinBookNATS(
            url=os.environ.get("NATS_URL", "nats://nats:4222"),
            service_name=settings.service_name,
            service_version=settings.service_version,
        )
        await nats.connect()
        await nats.ensure_stream()
        logger.info("[startup] NATS connected")
    except Exception as e:
        logger.exception(f"[startup] NATS init failed: {e}")
        nats = None

    # 4. DLQ publisher + monitor components
    if nats:
        dlq_publisher = DLQPublisher(nats=nats)
        # 订阅 DLQ 事件做 syncing
        try:
            await nats.subscribe("minbook.dlq.pipeline.failed", dlq_syncer._handle_pipeline_failed if dlq_syncer else _noop_handler)
            await nats.subscribe("minbook.dlq.node.failed", dlq_syncer._handle_node_failed if dlq_syncer else _noop_handler)
        except Exception as e:
            logger.debug(f"NATS subscribe failed (non-fatal in dev): {e}")

    heartbeat_monitor = HeartbeatMonitor(inactive_threshold_seconds=settings.agent_inactive_threshold_seconds)
    stale_scanner = StaleScanner(stale_threshold_seconds=settings.pipeline_stale_threshold_seconds)
    dlq_syncer = DLQSyncer()

    scheduler_queue = asyncio.Queue()

    # 5. 启动后台任务
    if nats:
        _background_tasks.append(asyncio.create_task(_run_scheduler()))
    _background_tasks.append(asyncio.create_task(heartbeat_monitor.run_forever()))
    _background_tasks.append(asyncio.create_task(stale_scanner.run_forever(scan_interval=settings.stale_scan_interval_seconds)))
    _background_tasks.append(asyncio.create_task(dlq_syncer.run_forever()))

    # 6. 订阅 cancel 事件
    if nats:
        async def _handle_cancel_event(event_data: dict):
            run_id = event_data.get("data", {}).get("pipeline_run_id")
            reason = event_data.get("data", {}).get("reason", "user_requested")
            if run_id:
                from .saga.cancellation import cancel_run
                await cancel_run(run_id, reason)

        try:
            await nats.subscribe("minbook.pipeline.*.cancel", _handle_cancel_event)
        except Exception as e:
            logger.debug(f"NATS cancel subscribe failed: {e}")

    logger.info(f"[startup] {settings.service_name} ready, {len(_background_tasks)} bg tasks started")

    yield

    # shutdown
    logger.info(f"[shutdown] {settings.service_name} stopping")
    for task in _background_tasks:
        task.cancel()
    for task in _background_tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"Background task exit: {e}")
    _background_tasks.clear()

    if nats:
        try:
            await nats.close()
        except Exception:
            pass

    try:
        await close_db()
    except Exception:
        pass


async def _run_scheduler():
    """从 queue 取 PipelineRun,执行 DAG。"""
    from .dag.executor import DAGExecutor
    while True:
        run = await scheduler_queue.get()
        try:
            executor = DAGExecutor(run, dag_loader, nats, dlq_publisher)  # type: ignore
            # 同步执行(单次 scheduler 串行;多 run 并发由 queue + 多 worker 扩展)
            await executor.execute()
        except Exception as e:
            logger.exception(f"Scheduler: executor for run {run.get('id')} crashed: {e}")


async def _noop_handler(event: dict):
    pass


app = FastAPI(
    title=f"MinBook Pipeline Orchestrator",
    version=settings.service_version,
    lifespan=lifespan,
)
instrument_fastapi(app)
app.add_middleware(InternalAuthMiddleware)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": settings.service_version,
        "loaded_dags": dag_loader.list_ids() if dag_loader else [],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("SERVICE_PORT", "8002")))
