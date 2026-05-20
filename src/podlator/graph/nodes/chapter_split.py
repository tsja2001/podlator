"""节点：按主题切分章节。使用 DeepSeek V4-Flash。"""

from __future__ import annotations

import json
import re
from typing import Any

from podlator.config import Settings
from podlator.graph.nodes._base import node, node_logger
from podlator.graph.state import Chapter, PodlatorState
from podlator.prompts import load_prompt
from podlator.providers.llm import get_llm_provider


@node("chapter_split")
async def run(state: PodlatorState) -> dict[str, Any]:
    log = node_logger(state, "chapter_split")

    transcript_text = state.get("transcript_text", "")
    if not transcript_text:
        log.warning("empty_transcript")
        return {"chapters": []}

    duration = state.get("duration_seconds", 0)
    settings = Settings()
    provider = get_llm_provider(settings.llm_provider_summarize, settings)

    system, user_template = load_prompt("chapter_split")
    user = user_template.format(
        duration_seconds=duration,
        transcript_text=transcript_text,
    )

    result = await provider.complete(prompt=user, system=system)
    log.info(
        "chapter_split_completed",
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_usd=result.cost_usd,
    )

    raw_chapters = _parse_json_array(result.content)
    segments = state.get("transcript_segments", [])
    chapters = _build_chapters(raw_chapters, segments)

    log.info("chapters_parsed", chapter_count=len(chapters))
    return {"chapters": chapters}


def _parse_json_array(text: str) -> list[dict[str, Any]]:
    """从 LLM 输出中提取 JSON 数组，容忍前后有其他文字。"""
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON array found in LLM output")
    return json.loads(match.group())  # type: ignore[no-any-return]


def _build_chapters(
    raw: list[dict[str, Any]],
    segments: list[Any],
) -> list[Chapter]:
    """将 LLM 返回的章节 JSON 转为 Chapter 列表，并计算 segment_indices。"""
    chapters: list[Chapter] = []
    for i, ch in enumerate(raw):
        start = float(ch.get("start", 0))
        end = float(ch.get("end", 0))
        indices = _find_segment_indices(segments, start, end)
        chapters.append(
            {
                "index": i,
                "title": ch.get("title", f"Chapter {i + 1}"),
                "start": start,
                "end": end,
                "segment_indices": indices,
                "summary_zh": "",
            }
        )
    return chapters


def _find_segment_indices(segments: list[Any], start: float, end: float) -> list[int]:
    """找到时间窗口内的 segment 索引。"""
    indices = []
    for i, seg in enumerate(segments):
        seg_start = seg.get("start", 0)
        seg_end = seg.get("end", 0)
        if seg_end > start and seg_start < end:
            indices.append(i)
    return indices
