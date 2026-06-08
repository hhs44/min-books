"""OpenTelemetry SDK 初始化(每个服务 main.py 顶部调用 init_tracing)。"""
import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def init_tracing(service_name: str, service_version: str = "0.1.0"):
    """初始化 OTel SDK,所有服务共用。"""
    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
        "deployment.environment": os.environ.get("DEPLOY_ENV", "dev"),
    })
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(
        endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"),
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # 自动埋点
    HTTPXClientInstrumentor().instrument()
    SystemMetricsInstrumentor().instrument()
    # FastAPI 单独在 app 创建后调: FastAPIInstrumentor.instrument_app(app)


def instrument_fastapi(app):
    """FastAPI app 创建后调。"""
    FastAPIInstrumentor.instrument_app(app)


def instrument_sqlalchemy(engine):
    """SQLAlchemy engine 创建后调。"""
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    SQLAlchemyInstrumentor().instrument(engine=engine)


def get_tracer(name: str):
    return trace.get_tracer(name)
