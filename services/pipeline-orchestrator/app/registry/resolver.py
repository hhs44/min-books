"""解析 service 名 → HTTP endpoint(详见 v4 §Phase B Task 6)。"""
import os

# 简化:硬编码 port(实际从 agent registry 拿)
SERVICE_PORTS = {
    "gateway": 8000,
    "state-service": 8007,
    "llm-gateway": 8006,
    "notification-service": 8008,
    "agent-planner-service": 8003,
    "agent-writer-service": 8004,
    "agent-reviewer-service": 8005,
    "pipeline-orchestrator": 8002,
}


async def resolve_service_endpoint(service_name: str) -> str:
    """返回 http://{service_name}:{port} 形式的 URL。

    支持环境变量覆盖(例:SERVICE_PORT_AGENT_PLANNER_SERVICE=9000)。
    """
    env_key = f"SERVICE_PORT_{service_name.replace('-', '_').upper()}"
    env_port = os.environ.get(env_key)
    if env_port:
        return f"http://{service_name}:{int(env_port)}"
    port = SERVICE_PORTS.get(service_name, 8000)
    return f"http://{service_name}:{port}"
