"""节点：章节翻译+精简（并发）。

通过 steps/render_chinese.py 完成章节翻译。
短期兼容：每章摘要写回 summary_zh 供 polish_final 使用。
"""

from __future__ import annotations

from typing import Any

from podlator.config import Settings
from podlator.graph.nodes._base import node, node_logger
from podlator.graph.state import Chapter, PodlatorState
from podlator.steps.models import (
    ChapterDocument,
    ChapterModel,
    TranscriptDocument,
    TranscriptProviderMeta,
    TranscriptSegmentModel,
    TranscriptSource,
)
from podlator.steps.render_chinese import render_chinese


def _state_segments_to_models(
    segments: list[Any],
) -> list[TranscriptSegmentModel]:
    """将 PodlatorState 的 transcript_segments 转为 Pydantic 模型列表。"""
    return [
        TranscriptSegmentModel(
            index=i,
            start=s.get("start", 0.0),
            end=s.get("end", 0.0),
            text=s.get("text", ""),
            speaker=s.get("speaker"),
            confidence=s.get("confidence"),
        )
        for i, s in enumerate(segments)
    ]


def _state_chapters_to_models(chapters: list[Chapter]) -> list[ChapterModel]:
    """将 PodlatorState 的 chapters 转为 Pydantic 模型列表。"""
    return [
        ChapterModel(
            index=ch["index"],
            title=ch["title"],
            start=ch["start"],
            end=ch["end"],
            segment_indices=ch.get("segment_indices", []),
        )
        for ch in chapters
    ]


def _parse_chapter_markdown(md: str, chapters: list[Chapter]) -> list[str]:
    """从 render_chinese 输出的 Markdown 中提取每章摘要。

    按 ## 标题分割，匹配章节 title。
    """
    sections = md.split("\n## ")
    # 第一个 section 是文档标题，跳过
    summaries: list[str] = [""] * len(chapters)

    for section in sections[1:]:  # 跳过标题行
        lines = section.strip().split("\n", 1)
        if not lines:
            continue
        title = lines[0].strip()
        content = lines[1].strip() if len(lines) > 1 else ""
        # 匹配章节 title
        for ch in chapters:
            if ch["title"] == title:
                summaries[ch["index"]] = content
                break

    return summaries


@node("summarize_chapters")
async def run(state: PodlatorState) -> dict[str, Any]:
    log = node_logger(state, "summarize_chapters")

    chapters = state.get("chapters", [])
    segments_raw = state.get("transcript_segments", [])
    if not chapters:
        log.warning("no_chapters_to_summarize")
        return {"chapter_summaries": []}

    # 构建 steps 层的模型
    transcript = TranscriptDocument(
        source=TranscriptSource(
            title=state.get("title"),
            duration_seconds=state.get("duration_seconds"),
        ),
        provider=TranscriptProviderMeta(name=state.get("stt_provider", "unknown")),
        text=state.get("transcript_text", ""),
        segments=_state_segments_to_models(segments_raw),
    )

    chapters_doc = ChapterDocument(
        source_transcript=None,
        chapters=_state_chapters_to_models(chapters),
    )

    settings = Settings()
    markdown = await render_chinese(
        transcript,
        chapters_doc,
        mode="summary",
        provider_name=settings.llm_provider_summarize,
        settings=settings,
    )

    # 解析 Markdown 提取每章摘要，写回 summary_zh
    summaries = _parse_chapter_markdown(markdown, chapters)
    for i, summary in enumerate(summaries):
        if summary:
            chapters[i]["summary_zh"] = summary

    log.info(
        "summaries_completed",
        total_chapters=len(chapters),
        success_count=sum(1 for s in summaries if s),
    )
    return {
        "chapters": chapters,
        "chapter_summaries": summaries,
    }
