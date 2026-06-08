"""结构化 JSON 日志,每条带 trace_id 和 span_id。"""
import json
import logging
import os
import sys
from typing import Any

from opentelemetry import trace


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        span = trace.get_current_span()
        ctx = span.get_span_context() if span else None

        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": os.environ.get("OTEL_SERVICE_NAME"),
            "trace_id": format(ctx.trace_id, "032x") if ctx and ctx.trace_id else None,
            "span_id": format(ctx.span_id, "016x") if ctx and ctx.span_id else None,
        }
        # 业务上下文(从 extra 传入)
        for key in (
            "book_id", "chapter_num", "pipeline_run_id",
            "node_id", "agent_id", "error",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO"):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
