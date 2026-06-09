"""Pipeline Orchestrator 配置(详见 v4 plan §Phase A Task 1)。"""
from pathlib import Path

from minbook_common.config import Settings


class PipelineSettings(Settings):
    """Pipeline Orchestrator 专用配置。"""

    service_name: str = "pipeline-orchestrator"
    service_version: str = "0.4.0"
    service_port: int = 8002

    # DAG 定义文件目录
    dag_definitions_dir: Path = Path("/app/pipeline_definitions")

    # 调度参数
    max_concurrent_runs: int = 5           # 同时跑的 Pipeline Run 数
    max_concurrent_nodes_per_run: int = 3  # 单 Run 内并行节点数
    node_default_timeout_seconds: int = 180
    pipeline_stale_threshold_seconds: int = 300  # §11 §8
    agent_inactive_threshold_seconds: int = 90   # §4.3

    # 调度 cron 间隔
    stale_scan_interval_seconds: int = 60
    heartbeat_check_interval_seconds: int = 30


def get_settings() -> PipelineSettings:
    return PipelineSettings()
