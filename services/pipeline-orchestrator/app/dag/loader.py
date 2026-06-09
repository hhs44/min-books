"""加载 pipeline_definitions/*.yaml → PipelineDefinition(详见 v4 §Phase A Task 3)。"""
import logging
from pathlib import Path

import yaml
from minbook_common.models import PipelineDefinition, PipelineNode

logger = logging.getLogger(__name__)


class DAGLoader:
    """启动时从 YAML 目录加载所有 DAG。"""

    def __init__(self, definitions_dir: Path):
        self.definitions_dir = Path(definitions_dir)
        self.dags: dict[str, PipelineDefinition] = {}

    async def load_all(self):
        """启动时加载所有 .yaml 文件。"""
        if not self.definitions_dir.exists():
            logger.warning(f"DAG definitions dir does not exist: {self.definitions_dir}")
            return

        for yaml_file in sorted(self.definitions_dir.glob("*.yaml")):
            try:
                with open(yaml_file) as f:
                    data = yaml.safe_load(f)
                if not data:
                    logger.warning(f"Empty DAG file: {yaml_file}")
                    continue
                # edges 可能是 "a -> b" 字符串或 {src, dst} dict
                # PipelineDefinition 强类型为 list[dict],统一转 dict
                raw_edges = data.get("edges", []) or []
                normalized_edges = []
                for e in raw_edges:
                    if isinstance(e, str):
                        if "->" in e:
                            src, dst = e.split("->", 1)
                        elif "→" in e:
                            src, dst = e.split("→", 1)
                        else:
                            raise ValueError(f"Invalid edge string: {e!r}")
                        normalized_edges.append({"src": src.strip(), "dst": dst.strip()})
                    elif isinstance(e, dict):
                        normalized_edges.append(e)
                    else:
                        raise ValueError(f"Invalid edge: {e!r}")
                dag = PipelineDefinition(
                    id=data["id"],
                    description=data.get("description", ""),
                    version=data.get("version", 1),
                    nodes=[PipelineNode(**n) for n in data["nodes"]],
                    edges=normalized_edges,
                    config=data.get("config", {}),
                )
                self.dags[dag.id] = dag
                logger.info(f"Loaded DAG: {dag.id} ({len(dag.nodes)} nodes, {len(dag.edges)} edges) from {yaml_file.name}")
            except Exception as e:
                logger.exception(f"Failed to load DAG from {yaml_file}: {e}")
                raise

    def get(self, dag_id: str) -> PipelineDefinition | None:
        return self.dags.get(dag_id)

    def list_ids(self) -> list[str]:
        return list(self.dags.keys())
