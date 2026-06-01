"""节点：按主题切分章节。

通过 steps/split_chapters.py 调用 LLM，prompt 包含时间戳。
"""

from __future__ import annotations

from typing import Any

from podlator.config import Settings
from podlator.graph.nodes._base import node, node_logger
from podlator.graph.state import PodlatorState
from podlator.steps.models import (
    TranscriptDocument,
    TranscriptProviderMeta,
    TranscriptSegmentModel,
    TranscriptSource,
)
from podlator.steps.split_chapters import split_transcript


@node("chapter_split")
async def run(state: PodlatorState) -> dict[str, Any]:
    log = node_logger(state, "chapter_split")

    transcript_text = state.get("transcript_text", "")
    segments_raw = state.get("transcript_segments", [])
    if not transcript_text or not segments_raw:
        log.warning("empty_transcript")
        return {"chapters": []}

    # 构建 TranscriptDocument
    segments = [
        TranscriptSegmentModel(
            index=i,
            start=s.get("start", 0.0),
            end=s.get("end", 0.0),
            text=s.get("text", ""),
            speaker=s.get("speaker"),
            confidence=s.get("confidence"),
        )
        for i, s in enumerate(segments_raw)
    ]

    transcript = TranscriptDocument(
        source=TranscriptSource(
            title=state.get("title"),
            duration_seconds=state.get("duration_seconds"),
        ),
        provider=TranscriptProviderMeta(name=state.get("stt_provider", "unknown")),
        text=transcript_text,
        segments=segments,
    )

    settings = Settings()
    chapters_doc = await split_transcript(
        transcript,
        provider_name=settings.llm_provider_summarize,
        settings=settings,
    )

    # 映射 ChapterDocument → PodlatorState (list[Chapter])
    chapters = [
        {
            "index": ch.index,
            "title": ch.title,
            "start": ch.start,
            "end": ch.end,
            "segment_indices": ch.segment_indices,
            "summary_zh": "",
        }
        for ch in chapters_doc.chapters
    ]

    log.info("chapters_parsed", chapter_count=len(chapters))
    return {"chapters": chapters}
