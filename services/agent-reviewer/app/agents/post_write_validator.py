"""PostWriteValidator:跨章重复检测 + 硬规则 spot-fix(详见 v2 §1.2)。

输入:本章内容 + 历史章节摘要(用于跨章重复检测)
输出:
  {
    "valid": bool,
    "issues": [...],
    "spot_fixes": [...],  # 已自动修复的项
    "duplicates": [...]   # 跨章重复片段
  }

纯逻辑 agent(不调 LLM),可被 pipeline 同步调用。
"""
from __future__ import annotations

import logging
import re

from minbook_common.agents.base import (
    AgentInput,
    AgentOutput,
    BaseAgent,
)
from minbook_common.agents.registry import register_agent

log = logging.getLogger(__name__)


# 硬规则:常见错别字 / 标点 spot-fix
HARD_RULES = [
    # 中文标点统一:中文字符间的半角逗号(可有空格) → 全角逗号
    (re.compile(r"([一-龥])\s*,\s*([一-龥])"), r"\1，\2", "warning", "中文字符间不应有空格+半角逗号"),
    (re.compile(r"([一-龥]),([一-龥])"), r"\1，\2", "warning", "中文字符间不应有半角逗号"),
    (re.compile(r"([一-龥])\s*\.\s*([一-龥])"), r"\1。\2", "warning", "中文句子结束应使用全角句号"),
    # 常见错别字
    (re.compile(r"做为"), "作为", "warning", "错别字:做为→作为"),
    (re.compile(r"帐号"), "账号", "warning", "推荐用词:帐号→账号"),
    # 多余的连续句号
    (re.compile(r"。{2,}"), "。", "warning", "连续多个句号"),
    (re.compile(r"\.{2,}\s*([一-龥])"), r"。\1", "warning", "英文省略号→中文省略号"),
]



# 跨章重复检测:句子级别 n-gram 重复
NGRAM_SIZE = 8  # 8 字符窗口


@register_agent
class PostWriteValidator(BaseAgent):
    name = "PostWriteValidator"
    version = "1.0.0"
    capabilities = ["post_write_validation", "cross_chapter_dedup", "hard_rule_spotfix"]
    memory_layers = []  # 纯逻辑

    async def run(self, input: AgentInput) -> AgentOutput:
        content = input.book_settings.get("content", "") or ""
        history_excerpts = input.book_settings.get("history_excerpts", []) or []

        issues: list[dict] = []
        spot_fixes: list[dict] = []
        fixed_content = content

        # 1. 硬规则 spot-fix
        for pattern, replacement, severity, desc in HARD_RULES:
            # 注意:pattern.subn(replacement_str, ...) 会处理 backreference(\1/\2)
            new_content, n = pattern.subn(replacement, fixed_content)
            if n > 0:
                spot_fixes.append({
                    "rule": desc,
                    "severity": severity,
                    "fixes_applied": n,
                })
                fixed_content = new_content

        # 2. 跨章重复检测
        duplicates: list[dict] = []
        if history_excerpts and fixed_content:
            current_ngrams = self._extract_ngrams(fixed_content, NGRAM_SIZE)
            for hist_idx, hist in enumerate(history_excerpts):
                if not isinstance(hist, str) or not hist:
                    continue
                hist_ngrams = self._extract_ngrams(hist, NGRAM_SIZE)
                overlap = current_ngrams & hist_ngrams
                if overlap:
                    # 取最长的几个 n-gram 作为代表
                    sample = sorted(overlap, key=len, reverse=True)[:3]
                    duplicates.append({
                        "history_index": hist_idx,
                        "overlap_ngrams": len(overlap),
                        "samples": sample,
                    })
                    issues.append({
                        "check": "cross_chapter_duplicate",
                        "severity": "major" if len(overlap) > 5 else "minor",
                        "history_index": hist_idx,
                        "overlap_count": len(overlap),
                    })

        if duplicates:
            log.info(
                "PostWriteValidator: found %d duplicate clusters across chapters",
                len(duplicates),
            )

        # 3. 简单长度 sanity
        if not fixed_content.strip():
            issues.append({
                "check": "content_empty",
                "severity": "critical",
                "message": "content is empty after spot-fix",
            })

        valid = not any(
            i.get("severity") == "critical" for i in issues
        )

        return AgentOutput(
            status="ok" if valid else "warning",
            result={
                "valid": valid,
                "issues": issues,
                "spot_fixes": spot_fixes,
                "duplicates": duplicates,
                "fixed_content": fixed_content if spot_fixes else content,
                "spot_fix_count": len(spot_fixes),
                "duplicate_count": len(duplicates),
            },
        )

    @staticmethod
    def _extract_ngrams(text: str, n: int) -> set[str]:
        """提取 n 字符 n-gram 集合(去空白)。"""
        # 去空白后切片
        clean = re.sub(r"\s+", "", text)
        if len(clean) < n:
            return {clean} if clean else set()
        return {clean[i:i + n] for i in range(len(clean) - n + 1)}
