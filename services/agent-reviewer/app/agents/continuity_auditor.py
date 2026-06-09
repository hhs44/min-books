"""ContinuityAuditor:对一章做 33 维度的连续性审计(详见 v2 §1.2)。

流程:
1. 加载全部 7 个真相文件(state-service)
2. 渲染 prompts/continuity_auditor.j2(章节 + 真相 + 33 维度)
3. 调 LLM(gpt-4o, temperature=0.3 稳定, max_tokens=4000)
4. 解析 JSON → AuditReport
5. 写 reviewer.audit_history(失败优雅降级)
6. 返 AuditReport

降级:
- LLM 解析失败 → status=error
- 真相文件缺失 → issues 收集,降级审计
- DB 写失败 → warning log + 继续
"""
from __future__ import annotations

import json
import logging
from uuid import UUID

from pydantic import BaseModel

from minbook_common.agents.base import (
    AgentInput,
    AgentOutput,
    BaseAgent,
)
from minbook_common.agents.registry import register_agent
from minbook_common.models import LLMChatRequest

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


class AuditIssue(BaseModel):
    """单条审计问题。"""

    severity: str  # critical | major | minor
    dimension: str  # 33 维度之一
    description: str
    location: str  # 章节内位置
    suggestion: str  # 修复建议


class AuditReport(BaseModel):
    """完整审计报告。"""

    issues: list[AuditIssue]
    overall_score: float  # 0-1
    critical_count: int
    major_count: int
    minor_count: int


@register_agent
class ContinuityAuditor(BaseAgent):
    name = "ContinuityAuditor"
    version = "1.0.0"
    capabilities = ["continuity_audit", "33_dimension_check"]
    memory_layers = ["semantic"]  # 历史错误模式

    # 33 个审计维度(详见 v2 §1.2 spec)
    DIMENSIONS = [
        "character_consistency", "character_voice", "character_arc",
        "timeline_consistency", "event_sequence", "temporal_logic",
        "world_rule_compliance", "magic_system_consistency", "setting_consistency",
        "plot_continuity", "subplot_progression", "foreshadowing_setup",
        "foreshadowing_payoff", "conflict_escalation", "tension_pacing",
        "narrative_pov", "tense_consistency", "point_of_view_shift",
        "style_consistency", "tone_consistency", "vocabulary_level",
        "dialogue_attribution", "show_vs_tell", "sentence_variety",
        "paragraph_flow", "chapter_arc", "scene_transitions",
        "hook_opening", "hook_ending", "cliffhanger_effect",
        "thematic_resonance", "motif_recurrence", "symbolic_coherence",
    ]

    async def run(self, input: AgentInput) -> AgentOutput:
        chapter_content = input.book_settings.get("content", "") or ""
        chapter_number = input.book_settings.get("chapter_number")

        # 1. 加载全部 7 个真相文件(失败降级为占位)
        truth_files = await self._load_all_truth(input.book_id)

        # 2. 渲染 prompt
        prompt = self.prompts.render(
            "continuity_auditor.j2",
            chapter_content=chapter_content,
            truth_files=truth_files,
            dimensions=self.DIMENSIONS,
        )

        # 3. 调 LLM
        try:
            response = await self.llm.chat(
                LLMChatRequest(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=4000,
                ),
                book_id=input.book_id,
                pipeline_run_id=input.pipeline_run_id,
                node_id=input.node_id,
                agent_id=self.name,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("ContinuityAuditor: LLM call failed: %s", e)
            return AgentOutput(
                status="error",
                error=f"LLM call failed: {e}",
            )

        # 4. 解析 JSON
        try:
            report_data = json.loads(response.content)
            report = AuditReport(**report_data)
        except Exception as e:  # noqa: BLE001
            log.warning("ContinuityAuditor: JSON parse failed: %s", e)
            return AgentOutput(
                status="error",
                error=f"Parse failed: {e}",
                result={"raw_content": response.content[:500]},
            )

        # 5. 写 reviewer.audit_history(失败优雅降级)
        await self._persist_audit(
            book_id=input.book_id,
            chapter_number=chapter_number,
            report=report,
        )

        return AgentOutput(
            status="ok",
            result=report.model_dump(),
            metrics={
                "tokens": response.usage,
                "cost_usd": float(response.cost_usd),
                "latency_ms": response.latency_ms,
            },
        )

    async def _load_all_truth(self, book_id: UUID) -> dict:
        """加载全部 7 个真相文件;任一失败 → 占位 {}。"""
        truth: dict = {}
        for file_type in TRUTH_FILE_TYPES:
            try:
                truth[file_type] = await self.state.get_truth(book_id, file_type)
            except Exception as e:  # noqa: BLE001
                log.warning(
                    "ContinuityAuditor: get_truth(%s) failed: %s", file_type, e,
                )
                truth[file_type] = {"_missing": True, "error": str(e)}
        return truth

    async def _persist_audit(
        self,
        book_id: UUID,
        chapter_number: int | None,
        report: AuditReport,
    ) -> None:
        """写 reviewer.audit_history,失败仅 warning。"""
        try:
            pool = self.memory.pool  # raises if _pool is None
        except Exception as e:  # noqa: BLE001
            log.warning("ContinuityAuditor: memory.pool unavailable: %s", e)
            return

        severity = (
            "critical" if report.critical_count > 0
            else "major" if report.major_count > 0
            else "minor"
        )

        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO reviewer.audit_history
                       (book_id, chapter_number, issues_json, severity)
                       VALUES ($1, $2, $3, $4)""",
                    book_id,
                    chapter_number,
                    json.dumps([i.model_dump() for i in report.issues]),
                    severity,
                )
        except Exception as e:  # noqa: BLE001
            log.warning("ContinuityAuditor: audit_history insert failed: %s", e)
