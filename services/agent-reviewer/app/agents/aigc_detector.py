"""AIGCDetector:AI 生成内容检测(详见 v2 §1.2)。

本期实现:基于规则的启发式检测(可后续接 ML 模型 / 远程 API)。
启发式特征:
- 高频 AI 标志词("作为一个AI"、"让我们"、"值得注意的是")
- 句长分布异常(平均句长 < 8 字 → 短碎;> 50 字 → 冗长)
- 段落长度方差过低(每段都差不多长 → AI 模板感)
- 感叹号 / 问号缺失(AI 文本极少)
- 段落首句模式重复(AI 喜欢用「首先/其次/最后」)

返:
  {
    "is_aigc": bool,  # 是否判定为 AI 生成
    "confidence": 0.0-1.0,
    "signals": [{"signal": "...", "weight": 0.2, "matched": true}, ...]
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


# AI 文本常见标志词(中英)
AIGC_PATTERNS: list[tuple[re.Pattern, str, float]] = [
    (re.compile(r"作为一个(AI|人工智能|大型语言模型)"), "self_reference_as_ai", 0.4),
    (re.compile(r"让我(们|来)?(探讨|分析|讨论)"), "phrases_let_us_explore", 0.15),
    (re.compile(r"值得注意的是"), "phrase_noteworthy", 0.1),
    (re.compile(r"首先.{0,5},?\s*其次.{0,5},?\s*最后"), "firstly_then_finally", 0.2),
    (re.compile(r"综上所述"), "phrase_in_conclusion", 0.1),
    (re.compile(r"总而言之"), "phrase_in_summary", 0.1),
    (re.compile(r"此外,?\s"), "phrase_moreover", 0.05),
    (re.compile(r"因此,?\s"), "phrase_therefore", 0.05),
    (re.compile(r"然而,?\s"), "phrase_however", 0.05),
    (re.compile(r"希望(这|本)(篇|文|章)?(对|能)你(有所|有)(帮助|启发|益处)"), "phrase_hope_helps", 0.15),
    (re.compile(r"^(In conclusion|To summarize|It's important to note)", re.MULTILINE), "english_meta", 0.15),
]


@register_agent
class AIGCDetector(BaseAgent):
    name = "AIGCDetector"
    version = "1.0.0"
    capabilities = ["aigc_detection", "ai_text_heuristics"]
    memory_layers = []  # 纯规则

    async def run(self, input: AgentInput) -> AgentOutput:
        content = input.book_settings.get("content", "") or ""
        if not content:
            return AgentOutput(
                status="error",
                error="AIGCDetector: missing 'content'",
            )

        signals: list[dict] = []
        score = 0.0

        # 1. 标志词检测
        for pattern, name, weight in AIGC_PATTERNS:
            matched = bool(pattern.search(content))
            if matched:
                score += weight
            signals.append({
                "signal": name,
                "weight": weight,
                "matched": matched,
            })

        # 2. 句长分布
        sentences = [s for s in re.split(r"[。！？!?]+", content) if s.strip()]
        if sentences:
            lengths = [len(s) for s in sentences]
            avg_len = sum(lengths) / len(lengths)
            signals.append({
                "signal": "avg_sentence_length",
                "value": avg_len,
                "matched": avg_len < 8 or avg_len > 50,
            })
            if avg_len < 8 or avg_len > 50:
                score += 0.1

            # 句长方差过低(全部很相近 → 模板感)
            if len(lengths) >= 5:
                mean = avg_len
                variance = sum((x - mean) ** 2 for x in lengths) / len(lengths)
                std = variance ** 0.5
                signals.append({
                    "signal": "sentence_length_std",
                    "value": std,
                    "matched": std < 3,
                })
                if std < 3:
                    score += 0.1

        # 3. 段落长度方差
        paragraphs = [p for p in re.split(r"\n+", content) if p.strip()]
        if len(paragraphs) >= 3:
            p_lengths = [len(p) for p in paragraphs]
            p_mean = sum(p_lengths) / len(p_lengths)
            p_var = sum((x - p_mean) ** 2 for x in p_lengths) / len(p_lengths)
            p_std = p_var ** 0.5
            signals.append({
                "signal": "paragraph_length_std",
                "value": p_std,
                "matched": p_std < 20,
            })
            if p_std < 20:
                score += 0.1

        # 4. 标点多样性
        punct_types = set(c for c in content if c in "。！？，、;；…——")
        if len(punct_types) < 2:
            signals.append({
                "signal": "punctuation_diversity_low",
                "value": len(punct_types),
                "matched": True,
            })
            score += 0.05
        else:
            signals.append({
                "signal": "punctuation_diversity_low",
                "value": len(punct_types),
                "matched": False,
            })

        # 限制到 [0, 1]
        confidence = min(1.0, score)
        is_aigc = confidence >= 0.5

        return AgentOutput(
            status="ok",
            result={
                "is_aigc": is_aigc,
                "confidence": round(confidence, 3),
                "signals": signals,
                "matched_signals": sum(1 for s in signals if s.get("matched")),
                "total_signals": len(signals),
                "content_length": len(content),
            },
        )
