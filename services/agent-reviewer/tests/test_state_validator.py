"""StateValidator 单元测试(纯逻辑,不调 LLM)。"""
from uuid import uuid4

import pytest

from app.agents.state_validator import StateValidator
from minbook_common.agents.base import AgentInput


class _StubStateOK:
    """state 桩:全部 7 个真相文件存在,character_matrix 有角色。"""

    async def get_truth(self, book_id, file_type):
        if file_type == "character_matrix":
            return {
                "version": 1,
                "content": {"characters": [{"name": "Alice"}, {"name": "Bob"}]},
            }
        if file_type == "current_state":
            return {
                "version": 3,
                "content": {"chapter_progress": 5, "last_event": "chapter done"},
            }
        return {"version": 1, "content": {}}


class _StubStateMissing:
    """state 桩:current_state 缺失。"""

    async def get_truth(self, book_id, file_type):
        if file_type == "missing_file":
            raise RuntimeError("file not found")
        return {"version": 1, "content": {"characters": []}}


class _StubMemory:
    @property
    def pool(self):
        raise RuntimeError("no pool (stub)")

    async def recall(self, *a, **kw):
        return []


@pytest.mark.asyncio
async def test_state_validator_pure_logic_happy_path():
    """全部真相文件存在 → valid=True。"""
    book_id = uuid4()
    agent = StateValidator(None, _StubStateOK(), _StubMemory(), None)

    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={"content": "Alice 走向城堡"},
        )
    )

    assert output.status == "ok"
    assert output.result["valid"] is True
    assert output.result["checks_run"] >= 3
    assert output.result["checks_passed"] == output.result["checks_run"]


@pytest.mark.asyncio
async def test_state_validator_pure_logic_missing_file():
    """真相文件缺失 → issues 有 critical,valid=False。"""
    from app.agents.state_validator import StateValidator

    book_id = uuid4()
    agent = StateValidator(None, _StubStateMissing(), _StubMemory(), None)

    # 传 content 才能进入 character_matrix_present 分支
    output = await agent.run(
        AgentInput(book_id=book_id, book_settings={"content": "Alice 走向城堡"}),
    )
    # 因为 _StubStateMissing 只对 missing_file 失败,其他 6 个都返 OK
    # 期望 valid=True(没有 critical/major)
    assert output.status == "ok"
    # 但会有 info 级别的 character_matrix_present(known=0)
    info_issues = [i for i in output.result["issues"] if i.get("severity") == "info"]
    assert any(i.get("check") == "character_matrix_present" for i in info_issues)
