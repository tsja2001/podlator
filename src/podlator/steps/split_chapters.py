# ruff: noqa: E501  (long prompt strings)
"""Step: Transcript JSON → Chapters JSON。

通过 LLM 按主题切分章节。Prompt 输入包含时间戳，
输出仅包含章节结构（start/end + title），不翻译、不摘要、不润色正文。
"""

from __future__ import annotations

import json
from typing import Any

from podlator.config import Settings
from podlator.logging import get_logger
from podlator.providers.llm import get_llm_provider
from podlator.steps.models import (
    ChapterDocument,
    ChapterModel,
    TranscriptDocument,
    TranscriptSegmentModel,
)

logger = get_logger(__name__)

_SPLIT_SYSTEM_PROMPT = """You are a podcast content structure analyst. Your ONLY job is to segment a transcript into topic-based chapters.

Rules:
1. You can ONLY output chapter boundaries — start time, end time, and a short Chinese title.
2. You CANNOT translate, summarize, or rewrite any transcript text.
3. You CANNOT output verbatim transcript excerpts.
4. Use the provided timestamps exactly — start should be at or near a segment's start time, end at or near a segment's end time.
5. Each chapter should cover a coherent topic. Typical chapter length: 2-8 minutes.
6. Cover the ENTIRE duration — no gaps between chapters.

Output a JSON array of chapter objects ONLY. No additional text."""

_SPLIT_USER_TEMPLATE = """Segment this transcript into topic-based chapters.

Total duration: {duration_seconds:.0f} seconds

Transcript segments:
{segments_text}

Output ONLY a JSON array:
[{{"title": "开场介绍", "start": 0.0, "end": 120.5}}, ...]"""


def _format_segments_with_timestamps(
    segments: list[TranscriptSegmentModel],
) -> str:
    """将 segments 格式化为带时间戳的文本，供 LLM 切分章节。"""
    lines = []
    for seg in segments:
        speaker = seg.speaker or "unknown"
        lines.append(f"[{seg.start:.2f} - {seg.end:.2f}] {speaker}: {seg.text}")
    return "\n".join(lines)


def _compute_segment_indices(
    chapters: list[dict[str, Any]],
    segments: list[TranscriptSegmentModel],
) -> list[list[int]]:
    """根据章节时间边界计算每个章节包含的 segment indices。"""
    results: list[list[int]] = []
    for ch in chapters:
        indices = [
            seg.index
            for seg in segments
            if seg.start >= ch["start"] - 0.5 and seg.end <= ch["end"] + 0.5
        ]
        if not indices:
            # 宽松匹配：至少包含 start 在范围内的
            indices = [
                seg.index for seg in segments if ch["start"] <= seg.start < ch["end"]
            ]
        results.append(indices)
    return results


async def split_transcript(
    transcript: TranscriptDocument,
    *,
    provider_name: str = "deepseek",
    settings: Settings | None = None,
) -> ChapterDocument:
    """将转录文本按主题切分为章节。

    输入要求：
    - transcript.segments 必须有时间戳信息。

    输出：
    - ChapterDocument，只包含章节结构（start/end + title）。
    - 不翻译、不摘要、不润色正文。

    Args:
        transcript: 输入 TranscriptDocument。
        provider_name: LLM provider 名称。
        settings: 应用配置。

    Returns:
        ChapterDocument。

    Raises:
        ValueError: segments 为空或 LLM 返回非法 JSON。
    """
    if not transcript.segments:
        raise ValueError("Transcript segments 为空，无法切分章节")

    if settings is None:
        settings = Settings()

    provider = get_llm_provider(provider_name, settings)

    segments_text = _format_segments_with_timestamps(transcript.segments)
    duration = transcript.source.duration_seconds or transcript.segments[-1].end

    prompt = _SPLIT_USER_TEMPLATE.format(
        duration_seconds=duration, segments_text=segments_text
    )

    result = await provider.complete(
        prompt,
        system=_SPLIT_SYSTEM_PROMPT,
        temperature=0.3,
        max_tokens=4096,
    )

    content = result.content.strip()
    # LLM 可能会包裹在 ```json ``` 中
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        raw_chapters = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"LLM 章节切分返回非法 JSON: {e}\ncontent: {content[:500]}"
        ) from e

    if not isinstance(raw_chapters, list):
        raise ValueError(
            f"LLM 章节切分返回非数组: {type(raw_chapters)}\ncontent: {content[:500]}"
        )

    # 计算每个章节的 segment_indices
    segment_indices_list = _compute_segment_indices(raw_chapters, transcript.segments)

    chapters = []
    for i, ch_dict in enumerate(raw_chapters):
        chapters.append(
            ChapterModel(
                index=i,
                title=ch_dict.get("title", f"Chapter {i + 1}"),
                start=ch_dict.get("start", 0.0),
                end=ch_dict.get("end", 0.0),
                segment_indices=segment_indices_list[i]
                if i < len(segment_indices_list)
                else [],
            )
        )

    return ChapterDocument(chapters=chapters)
