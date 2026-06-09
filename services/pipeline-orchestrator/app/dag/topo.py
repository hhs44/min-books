"""DAG 拓扑排序 + 并行分组识别(详见 v4 §Phase A Task 3)。"""
import logging
from collections import defaultdict

import networkx as nx
from minbook_common.models import PipelineDefinition

logger = logging.getLogger(__name__)


class DAGAnalyzer:
    """DAG 分析器:用 networkx 做拓扑排序、依赖查询、并行组识别。"""

    def __init__(self, dag: PipelineDefinition):
        self.dag = dag
        self.graph = nx.DiGraph()
        for node in dag.nodes:
            self.graph.add_node(node.id)
        for edge in dag.edges:
            # edge 可能是 "a -> b" 字符串或 {"src": "a", "dst": "b"} dict
            if isinstance(edge, str):
                src, dst = self._parse_edge_string(edge)
            elif isinstance(edge, dict):
                src = edge.get("src") or edge.get("source") or edge.get("from")
                dst = edge.get("dst") or edge.get("dest") or edge.get("to") or edge.get("target")
                if not src or not dst:
                    raise ValueError(f"Invalid edge dict: {edge}")
            else:
                raise ValueError(f"Invalid edge type: {type(edge)}")
            self.graph.add_edge(src, dst)

    @staticmethod
    def _parse_edge_string(edge: str) -> tuple[str, str]:
        if "->" in edge:
            src, dst = edge.split("->", 1)
        elif "→" in edge:
            src, dst = edge.split("→", 1)
        else:
            raise ValueError(f"Invalid edge string: {edge!r}")
        return src.strip(), dst.strip()

    def topological_order(self) -> list[str]:
        """返回节点 ID 的拓扑排序(失败时 raise)。"""
        if not nx.is_directed_acyclic_graph(self.graph):
            cycles = list(nx.simple_cycles(self.graph))
            raise ValueError(f"DAG has cycle: {cycles}")
        return list(nx.topological_sort(self.graph))

    def parallel_groups(self) -> dict[str, list[str]]:
        """识别可并行的节点组(由节点的 `parallel_group` 字段标识)。

        Returns: {group_name: [node_id, ...]}
        """
        groups: dict[str, list[str]] = defaultdict(list)
        for node in self.dag.nodes:
            if node.parallel_group:
                groups[node.parallel_group].append(node.id)
        return dict(groups)

    def next_ready_nodes(self, completed: set[str]) -> list[str]:
        """返回下一批可执行的节点(依赖都已 completed + 节点未完成)。

        注:同一并行组内的节点会一起返回,由调用方决定是否用 asyncio.gather 并行。
        """
        ready = []
        for node in self.dag.nodes:
            if node.id in completed:
                continue
            deps_satisfied = all(
                dep in completed
                for dep in self._incoming(node.id)
            )
            if deps_satisfied:
                ready.append(node.id)
        return ready

    def _incoming(self, node_id: str) -> list[str]:
        return [src for src, _ in self.graph.in_edges(node_id)]

    def get_node(self, node_id: str):
        for n in self.dag.nodes:
            if n.id == node_id:
                return n
        return None
