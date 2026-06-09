"""SettlerAgent 单元测试(用桩 state 模拟 create_snapshot + update_truth)。"""
from uuid import uuid4

import pytest

from app.agents.settler import SettlerAgent
from minbook_common.agents.base import AgentInput


class _StubStateWorking:
    """state 桩:create_snapshot 返 ID,get_truth/update_truth 工作正常。"""

    def __init__(self):
        self.calls = {"snapshot": 0, "update": 0, "get": 0}
        self.versions = {"current_state": 2, "character_matrix": 1}
        # 注意:contents 每次 get 都返回新 dict(避免 Settler 内部 {**} 合并后污染源数据)
        self.contents = {
            "current_state": {"chapter_progress": 3, "last_event": "old"},
            "character_matrix": {"characters": [{"name": "Alice"}]},
        }

    async def create_snapshot(self, book_id, chapter_number, snapshot_json):
        self.calls["snapshot"] += 1
        return {"snapshot_id": "snap-123"}

    async def get_truth(self, book_id, file_type):
        self.calls["get"] += 1
        if file_type in self.contents:
            return {
                "version": self.versions.get(file_type, 0),
                "content": dict(self.contents[file_type]),  # copy
            }
        raise RuntimeError(f"not found: {file_type}")

    async def update_truth(self, book_id, file_type, content, expected_version=None):
        self.calls["update"] += 1
        self.versions[file_type] = (self.versions.get(file_type, 0)) + 1
        # 真的写回 contents
        self.contents[file_type] = dict(content)
        return {"version": self.versions[file_type]}


class _StubMemory:
    @property
    def pool(self):
        raise RuntimeError("no pool (stub)")

    async def recall(self, *a, **kw):
        return []


@pytest.mark.asyncio
async def test_settler_creates_snapshot_then_writes_delta():
    """1. 创建 snapshot,2. 逐 file 调 update_truth(expected_version 乐观并发)。"""
    book_id = uuid4()
    state = _StubStateWorking()
    agent = SettlerAgent(None, state, _StubMemory(), None)

    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={
                "delta": {
                    "current_state": {"last_event": "Alice 找到剑"},
                    "character_matrix": {"updates": [{"name": "Bob", "status": "ally"}]},
                },
                "chapter_number": 5,
            },
        )
    )

    assert output.status == "ok", output.error
    assert output.result["snapshot_id"] == "snap-123"
    assert state.calls["snapshot"] == 1
    assert state.calls["update"] == 2  # 两个真相文件都被写
    assert state.calls["get"] == 2     # 写前都 get 拿 version
    assert output.result["written_count"] == 2
    assert output.result["failed_count"] == 0
    # 合并后 current_state 应有新的 last_event
    assert state.contents["current_state"]["last_event"] == "Alice 找到剑"


@pytest.mark.asyncio
async def test_settler_no_delta_returns_error():
    """缺 delta → 不创 snapshot,直接 status=error。"""
    book_id = uuid4()
    state = _StubStateWorking()
    agent = SettlerAgent(None, state, _StubMemory(), None)

    output = await agent.run(AgentInput(book_id=book_id, book_settings={}))

    assert output.status == "error"
    assert state.calls["snapshot"] == 0
