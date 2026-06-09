"""SettlerAgent:把 ObserverAgent 的 delta 写入 state-service(详见 v2 §1.2)。

两阶段:
1. 创建 snapshot(写前快照,便于审计回滚)
2. 写 delta 到 state.truth_files(乐观并发:expected_version)

降级:
- snapshot 失败 → 返回 status=error(谨慎处理)
- 单个 update_truth 失败 → issues 记录该文件,继续下一个
"""
from __future__ import annotations

import logging

from minbook_common.agents.base import (
    AgentInput,
    AgentOutput,
    BaseAgent,
)
from minbook_common.agents.registry import register_agent

log = logging.getLogger(__name__)


# 与 ObserverAgent 同步
DELTA_TARGETS = [
    "current_state",
    "character_matrix",
    "pending_hooks",
    "chapter_summaries",
    "subplot_board",
    "emotional_arcs",
    "particle_ledger",
]


@register_agent
class SettlerAgent(BaseAgent):
    name = "SettlerAgent"
    version = "1.0.0"
    capabilities = ["truth_writing", "snapshot_management"]
    memory_layers = []

    async def run(self, input: AgentInput) -> AgentOutput:
        delta = input.book_settings.get("delta", {}) or {}
        chapter_number = input.book_settings.get("chapter_number")
        book_id = input.book_id

        if not delta:
            return AgentOutput(
                status="error",
                error="SettlerAgent: missing 'delta'",
            )

        # 1. 创建写前 snapshot
        snapshot_id: str | None = None
        try:
            snapshot = await self.state.create_snapshot(
                book_id=book_id,
                chapter_number=chapter_number,
                snapshot_json={"pre_settle": True, "delta_keys": list(delta.keys())},
            )
            snapshot_id = (
                snapshot.get("snapshot_id")
                or snapshot.get("id")
                or (snapshot.get("content", {}) or {}).get("snapshot_id")
            )
        except Exception as e:  # noqa: BLE001
            log.warning("SettlerAgent: create_snapshot failed: %s", e)
            return AgentOutput(
                status="error",
                error=f"Snapshot creation failed: {e}",
                result={"delta_keys": list(delta.keys())},
            )

        # 2. 应用 delta(逐个真相文件)
        written: list[dict] = []
        failed: list[dict] = []

        for file_type, content_delta in delta.items():
            if file_type not in DELTA_TARGETS:
                log.warning(
                    "SettlerAgent: skipping unknown truth file '%s'", file_type,
                )
                failed.append({
                    "file_type": file_type,
                    "reason": "unknown_truth_file",
                })
                continue

            if not isinstance(content_delta, dict):
                failed.append({
                    "file_type": file_type,
                    "reason": "delta_not_dict",
                })
                continue

            try:
                # 2a. 读 current(拿 version)
                current: dict = {}
                current_version: int | None = None
                try:
                    current = await self.state.get_truth(book_id, file_type)
                    current_version = current.get("version") if isinstance(current, dict) else None
                except Exception as e:  # noqa: BLE001
                    log.warning(
                        "SettlerAgent: get_truth(%s) failed (will create fresh): %s",
                        file_type, e,
                    )

                # 2b. 合并 delta(simplified shallow merge)
                current_content = (
                    current.get("content", {}) if isinstance(current, dict) else {}
                )
                if not isinstance(current_content, dict):
                    current_content = {}
                new_content = {**current_content, **content_delta}

                # 2c. update_truth(乐观并发)
                result = await self.state.update_truth(
                    book_id=book_id,
                    file_type=file_type,
                    content=new_content,
                    expected_version=current_version,
                )
                written.append({
                    "file_type": file_type,
                    "new_version": result.get("version") if isinstance(result, dict) else None,
                })
            except Exception as e:  # noqa: BLE001
                log.warning(
                    "SettlerAgent: update_truth(%s) failed: %s", file_type, e,
                )
                failed.append({
                    "file_type": file_type,
                    "reason": str(e),
                })

        return AgentOutput(
            status="ok" if not failed else "warning",
            result={
                "snapshot_id": snapshot_id,
                "written": written,
                "failed": failed,
                "written_count": len(written),
                "failed_count": len(failed),
            },
        )
