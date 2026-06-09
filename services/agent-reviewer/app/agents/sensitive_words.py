"""SensitiveWordsDetector:敏感词检测(详见 v2 §1.2)。

本期实现:内置默认敏感词库(可被 book_settings.sensitive_words 覆盖)。
可后续接远程词库 API / 自定义 .txt 文件。

返:
  {
    "found": [{"word": "...", "count": 3, "category": "..."}],
    "total_matches": int,
    "categories": {category: count}
  }
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


# 内置默认敏感词库(按 category 分组)
DEFAULT_WORD_BANK: dict[str, list[str]] = {
    "violence": [
        "血腥", "残忍", "酷刑", "屠杀",
    ],
    "politics": [
        "颠覆", "政权", "暴动",
    ],
    "adult": [
        "色情", "裸体", "性交",
    ],
    "drugs": [
        "毒品", "海洛因", "冰毒",
    ],
    "discrimination": [
        "种族歧视", "性别歧视",
    ],
    "pii": [
        # PII patterns 由 regex 处理,这里仅占位
    ],
}

# 简单 PII 正则
PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("pii_id_card", re.compile(r"\b\d{17}[\dXx]\b")),  # 中国身份证
    ("pii_phone", re.compile(r"\b1[3-9]\d{9}\b")),       # 中国手机号
    ("pii_email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
]


@register_agent
class SensitiveWordsDetector(BaseAgent):
    name = "SensitiveWordsDetector"
    version = "1.0.0"
    capabilities = ["sensitive_words_detection", "pii_detection"]
    memory_layers = []  # 纯规则

    async def run(self, input: AgentInput) -> AgentOutput:
        content = input.book_settings.get("content", "") or ""
        if not content:
            return AgentOutput(
                status="error",
                error="SensitiveWordsDetector: missing 'content'",
            )

        # 词库:可被 input 覆盖
        word_bank: dict[str, list[str]] = DEFAULT_WORD_BANK
        override = input.book_settings.get("sensitive_words")
        if isinstance(override, dict) and override:
            word_bank = {**DEFAULT_WORD_BANK, **override}

        found: list[dict] = []
        categories: dict[str, int] = {}
        total_matches = 0

        # 1. 词库扫描
        for category, words in word_bank.items():
            if not words:
                continue
            for word in words:
                if not word:
                    continue
                count = content.count(word)
                if count > 0:
                    found.append({
                        "word": word,
                        "count": count,
                        "category": category,
                    })
                    categories[category] = categories.get(category, 0) + count
                    total_matches += count

        # 2. PII 正则扫描
        for name, pattern in PII_PATTERNS:
            matches = pattern.findall(content)
            if matches:
                found.append({
                    "word": f"<{name}>",
                    "count": len(matches),
                    "category": "pii",
                    "samples": matches[:3],  # 最多保留 3 个样本
                })
                categories["pii"] = categories.get("pii", 0) + len(matches)
                total_matches += len(matches)

        flagged = total_matches > 0

        return AgentOutput(
            status="ok",
            result={
                "found": found,
                "total_matches": total_matches,
                "categories": categories,
                "flagged": flagged,
                "categories_hit": list(categories.keys()),
                "content_length": len(content),
            },
        )
