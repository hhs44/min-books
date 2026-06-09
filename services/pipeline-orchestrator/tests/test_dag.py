"""DAG 解析 + 拓扑排序 + 并行组识别单元测试(v4 §Phase E Task 16)。"""
import pytest
from pathlib import Path

from app.dag.loader import DAGLoader
from app.dag.topo import DAGAnalyzer
from minbook_common.models import PipelineDefinition, PipelineNode


@pytest.fixture
def dag_dir(tmp_path):
    yaml_content = """
id: test_dag
description: 测试 DAG
version: 1
nodes:
  - id: a
  - id: b
    parallel_group: g1
  - id: c
    parallel_group: g1
  - id: d
edges:
  - a -> b
  - a -> c
  - b -> d
  - c -> d
"""
    f = tmp_path / "test_dag.yaml"
    f.write_text(yaml_content)
    return tmp_path


@pytest.mark.asyncio
async def test_load_dag(dag_dir):
    loader = DAGLoader(dag_dir)
    await loader.load_all()
    dag = loader.get("test_dag")
    assert dag is not None
    assert len(dag.nodes) == 4
    assert len(dag.edges) == 4


def test_topological_order():
    nodes = [
        PipelineNode(id="a"),
        PipelineNode(id="b", parallel_group="g1"),
        PipelineNode(id="c", parallel_group="g1"),
        PipelineNode(id="d"),
    ]
    edges = [{"src": "a", "dst": "b"}, {"src": "a", "dst": "c"},
             {"src": "b", "dst": "d"}, {"src": "c", "dst": "d"}]
    dag = PipelineDefinition(id="test", nodes=nodes, edges=edges)
    analyzer = DAGAnalyzer(dag)
    order = analyzer.topological_order()
    assert order[0] == "a"
    assert order[-1] == "d"
    # a 在 b/c 之前,b/c 在 d 之前
    assert order.index("a") < order.index("b")
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("d")
    assert order.index("c") < order.index("d")


def test_parallel_groups():
    nodes = [
        PipelineNode(id="a"),
        PipelineNode(id="b", parallel_group="g1"),
        PipelineNode(id="c", parallel_group="g1"),
    ]
    dag = PipelineDefinition(
        id="test", nodes=nodes,
        edges=[{"src": "a", "dst": "b"}, {"src": "a", "dst": "c"}],
    )
    analyzer = DAGAnalyzer(dag)
    groups = analyzer.parallel_groups()
    assert "g1" in groups
    assert set(groups["g1"]) == {"b", "c"}


def test_next_ready_nodes():
    nodes = [
        PipelineNode(id="a"),
        PipelineNode(id="b", parallel_group="g1"),
        PipelineNode(id="c", parallel_group="g1"),
        PipelineNode(id="d"),
    ]
    edges = [{"src": "a", "dst": "b"}, {"src": "a", "dst": "c"},
             {"src": "b", "dst": "d"}, {"src": "c", "dst": "d"}]
    dag = PipelineDefinition(id="test", nodes=nodes, edges=edges)
    analyzer = DAGAnalyzer(dag)

    # 初始 → 只有 a 可跑
    ready = analyzer.next_ready_nodes(set())
    assert ready == ["a"]

    # a 完成 → b, c 都可以跑
    ready = analyzer.next_ready_nodes({"a"})
    assert set(ready) == {"b", "c"}

    # a, b, c 都完成 → d 可以跑
    ready = analyzer.next_ready_nodes({"a", "b", "c"})
    assert ready == ["d"]


def test_cycle_raises():
    """有环的 DAG → topological_order 应该 raise。"""
    nodes = [PipelineNode(id="a"), PipelineNode(id="b")]
    edges = [{"src": "a", "dst": "b"}, {"src": "b", "dst": "a"}]  # cycle
    dag = PipelineDefinition(id="cycle", nodes=nodes, edges=edges)
    analyzer = DAGAnalyzer(dag)
    with pytest.raises(ValueError, match="cycle"):
        analyzer.topological_order()


def test_chapter_writing_v2_loads():
    """v4 实际部署的 chapter_writing_v2.yaml 应正确加载。"""
    import os
    yaml_path = Path(__file__).resolve().parent.parent / "pipeline_definitions" / "chapter_writing_v2.yaml"
    if not yaml_path.exists():
        pytest.skip(f"chapter_writing_v2.yaml not found at {yaml_path}")

    loader = DAGLoader(yaml_path.parent)
    import asyncio
    asyncio.run(loader.load_all())
    dag = loader.get("chapter_writing_v2")
    assert dag is not None
    assert len(dag.nodes) == 9
    # 拓扑顺序存在且合法
    order = DAGAnalyzer(dag).topological_order()
    assert order[0] == "plan"
    assert order[-1] == "save"
    # 并行组识别
    groups = DAGAnalyzer(dag).parallel_groups()
    assert "post_write" in groups
    assert set(groups["post_write"]) == {"observe", "audit", "settle"}
