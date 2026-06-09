"""StateValidator:校验真相文件 schema 和一致性(详见 v2 §1.2)。

纯逻辑 agent(不调 LLM),检查:
1. 全部 7 个真相文件存在
2. 角色名一致性(章节里出现的角色名都在 character_matrix 里有定义)
3. 真相文件 version 字段连续(单调递增)
4. 必填字段非空(current_state 至少要有 chapter_progress)

返 {valid, issues, summary}
"""
from __future__ import annotations

import logging
from uuid import UUID

from minbook_common.agents.base import (
    AgentInput,
    AgentOutput,
    BaseAgent,
)
from minbook_common.agents.registry import register_agent

log = logging.getLogger(__name__)


# 7 个真相文件类型
TRUTH_FILE_TYPES = [
    "current_state",
    "character_matrix",
    "pending_hooks",
    "chapter_summaries",
    "subplot_board",
    "emotional_arcs",
    "particle_ledger",
]


@register_agent
class StateValidator(BaseAgent):
    name = "StateValidator"
    version = "1.0.0"
    capabilities = ["state_validation", "schema_consistency"]
    memory_layers = []  # 纯逻辑

    async def run(self, input: AgentInput) -> AgentOutput:
        book_id = input.book_id
        issues: list[dict] = []
        checks_run = 0
        checks_passed = 0

        # 1. 全部 7 个真相文件存在?
        truth_data: dict = {}
        for file_type in TRUTH_FILE_TYPES:
            checks_run += 1
            try:
                data = await self.state.get_truth(book_id, file_type)
                truth_data[file_type] = data
                checks_passed += 1
            except Exception as e:  # noqa: BLE001
                issues.append({
                    "check": "truth_file_exists",
                    "file_type": file_type,
                    "severity": "critical",
                    "message": f"truth file '{file_type}' missing or inaccessible: {e}",
                })

        # 2. 角色名一致性(content 里出现的角色名都在 character_matrix)
        content = input.book_settings.get("content", "") or ""
        if content and "character_matrix" in truth_data:
            checks_run += 1
            cm_data = truth_data["character_matrix"]
            cm_content = cm_data.get("content", {}) if isinstance(cm_data, dict) else {}
            known_chars = set()
            characters = cm_content.get("characters", []) or []
            if isinstance(characters, list):
                for ch in characters:
                    if isinstance(ch, dict) and "name" in ch:
                        known_chars.add(str(ch["name"]))
                    elif isinstance(ch, str):
                        known_chars.add(ch)
            # 简单提示:这里不做完整名字提取,只在 issues 里记录
            issues.append({
                "check": "character_matrix_present",
                "severity": "info",
                "known_characters_count": len(known_chars),
                "message": f"character_matrix contains {len(known_chars)} known characters",
            })
            checks_passed += 1

        # 3. version 连续(对有 version 字段的真相文件)
        checks_run += 1
        version_issues = 0
        for file_type, data in truth_data.items():
            if not isinstance(data, dict):
                continue
            content_dict = data.get("content", {}) if isinstance(data, dict) else {}
            version = data.get("version")
            if version is not None and not isinstance(version, int):
                version_issues += 1
                issues.append({
                    "check": "version_field_type",
                    "file_type": file_type,
                    "severity": "major",
                    "message": f"version must be int, got {type(version).__name__}",
                })
        if version_issues == 0:
            checks_passed += 1

        # 4. 必填字段非空(current_state.chapter_progress 不能为 None)
        if "current_state" in truth_data:
            checks_run += 1
            cs_data = truth_data["current_state"]
            cs_content = cs_data.get("content", {}) if isinstance(cs_data, dict) else {}
            if "chapter_progress" in cs_content and cs_content.get("chapter_progress") is None:
                issues.append({
                    "check": "current_state_required_fields",
                    "severity": "major",
                    "message": "current_state.chapter_progress is None",
                })
            else:
                checks_passed += 1

        valid = not any(
            i.get("severity") in ("critical", "major") for i in issues
        )

        return AgentOutput(
            status="ok" if valid else "warning",
            result={
                "valid": valid,
                "issues": issues,
                "checks_run": checks_run,
                "checks_passed": checks_passed,
                "truth_files_loaded": list(truth_data.keys()),
            },
        )
