"""运行时共享状态容器(v4 §Phase D Task 10+)

解决 main.py ↔ routes/* 循环 import 问题:
- routes 需要读 scheduler_queue / dag_loader / nats
- main.py lifespan 负责赋值
- 路由模块 from .state import scheduler_queue ...
"""
import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .dag.loader import DAGLoader
    from .saga.dlq_publisher import DLQPublisher
    from minbook_common.nats_client import MinBookNATS

# 全局共享资源(由 main.lifespan 赋值)
dag_loader: "DAGLoader | None" = None
nats: "MinBookNATS | None" = None
dlq_publisher: "DLQPublisher | None" = None
scheduler_queue: asyncio.Queue | None = None
