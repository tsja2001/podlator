"""节点：章节翻译+精简（并发）。使用 DeepSeek V4-Flash。"""

from __future__ import annotations

import asyncio
from typing import Any

from podlator.config import Settings
from podlator.graph.nodes._base import node, node_logger
from podlator.graph.state import Chapter, PodlatorState, TranscriptSegment
from podlator.prompts import load_prompt
from podlator.providers.llm import get_llm_provider


@node("summarize_chapters")
async def run(state: PodlatorState) -> dict[str, Any]:
    log = node_logger(state, "summarize_chapters")

    chapters = state.get("chapters", [])
    segments = state.get("transcript_segments", [])
    if not chapters:
        log.warning("no_chapters_to_summarize")
        return {"chapter_summaries": []}

    settings = Settings()
    provider = get_llm_provider(settings.llm_provider_summarize, settings)
    system, user_template = load_prompt("summarize_chapter")

    sem = asyncio.Semaphore(5)

    async def summarize_one(ch: Chapter) -> tuple[int, str]:
        async with sem:
            chapter_text = _get_chapter_text(segments, ch)
            user = user_template.format(
                chapter_title=ch["title"],
                start=ch["start"],
                end=ch["end"],
                chapter_text=chapter_text,
            )
            result = await provider.complete(prompt=user, system=system)
            return ch["index"], result.content

    tasks = [summarize_one(ch) for ch in chapters]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    summaries: list[str] = [""] * len(chapters)
    total_cost = 0.0
    success_count = 0

    for i, r in enumerate(results):
        if isinstance(r, Exception):
            log.warning("chapter_summary_failed", chapter_index=i, error_msg=str(r))
        elif isinstance(r, tuple):
            idx, content = r
            chapters[idx]["summary_zh"] = content
            summaries[idx] = content
            success_count += 1

    log.info(
        "summaries_completed",
        total_chapters=len(chapters),
        success_count=success_count,
        cost_usd=total_cost,
    )
    return {
        "chapters": chapters,
        "chapter_summaries": summaries,
    }


def _get_chapter_text(segments: list[TranscriptSegment], chapter: Chapter) -> str:
    """拼接章节对应的转录片段文本。"""
    indices = chapter["segment_indices"]
    if not indices:
        return ""
    first = indices[0]
    last = indices[-1] + 1
    chapter_segments = segments[first:last]
    return " ".join(s["text"] for s in chapter_segments)
