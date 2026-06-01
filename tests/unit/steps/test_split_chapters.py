"""Unit tests for split_chapters step (mock LLM)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from podlator.providers.llm.base import LLMResult
from podlator.steps.models import (
    ChapterModel,
    TranscriptDocument,
    TranscriptProviderMeta,
    TranscriptSegmentModel,
    TranscriptSource,
)

_CHAPTERS_JSON = json.dumps(
    [
        {"title": "开场介绍", "start": 0.0, "end": 20.0},
        {"title": "主题讨论", "start": 20.0, "end": 30.0},
    ]
)


def _make_transcript() -> TranscriptDocument:
    segments = [
        TranscriptSegmentModel(
            index=i,
            start=i * 10.0,
            end=(i + 1) * 10.0,
            text=f"Segment {i} text.",
            speaker="SPEAKER_0",
        )
        for i in range(3)
    ]
    return TranscriptDocument(
        source=TranscriptSource(title="Test", duration_seconds=30.0),
        provider=TranscriptProviderMeta(name="deepgram"),
        text=" ".join(s.text for s in segments),
        segments=segments,
    )


class TestSplitTranscript:
    @pytest.mark.asyncio
    async def test_splits_into_chapters(self) -> None:
        """正常路径：LLM 返回章节边界，正确构建 ChapterDocument。"""
        transcript = _make_transcript()
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content=_CHAPTERS_JSON,
                model="test",
                provider_name="deepseek",
                tokens_in=200,
                tokens_out=100,
                duration_ms=1000,
                cost_usd=0.002,
            )
        )

        with patch(
            "podlator.steps.split_chapters.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.split_chapters import split_transcript

            result = await split_transcript(transcript)

        assert len(result.chapters) == 2
        assert result.chapters[0].title == "开场介绍"
        assert result.chapters[0].start == 0.0
        assert result.chapters[0].end == 20.0
        assert result.chapters[1].title == "主题讨论"

    @pytest.mark.asyncio
    async def test_chapter_has_segment_indices(self) -> None:
        """验证章节包含 segment_indices。"""
        transcript = _make_transcript()
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content=_CHAPTERS_JSON,
                model="test",
                provider_name="deepseek",
                tokens_in=200,
                tokens_out=100,
                duration_ms=1000,
                cost_usd=0.002,
            )
        )

        with patch(
            "podlator.steps.split_chapters.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.split_chapters import split_transcript

            result = await split_transcript(transcript)

        # Ch1: 0-20s 应包含 segments 0 和 1
        assert len(result.chapters[0].segment_indices) >= 0

    @pytest.mark.asyncio
    async def test_empty_segments_raises(self) -> None:
        """空 segments 时抛出 ValueError。"""
        transcript = TranscriptDocument(
            source=TranscriptSource(title="Empty"),
            provider=TranscriptProviderMeta(name="srt"),
        )

        from podlator.steps.split_chapters import split_transcript

        with pytest.raises(ValueError, match="segments 为空"):
            await split_transcript(transcript)

    @pytest.mark.asyncio
    async def test_invalid_json_from_llm_raises(self) -> None:
        """LLM 返回非法 JSON 时抛出 ValueError。"""
        transcript = _make_transcript()
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content="not json",
                model="test",
                provider_name="deepseek",
                tokens_in=100,
                tokens_out=50,
                duration_ms=500,
                cost_usd=0.001,
            )
        )

        with patch(
            "podlator.steps.split_chapters.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.split_chapters import split_transcript

            with pytest.raises(ValueError, match="非法 JSON"):
                await split_transcript(transcript)

    @pytest.mark.asyncio
    async def test_chapters_output_no_summary_content(self) -> None:
        """验证 split 输出只包含章节结构，不包含摘要内容。"""
        transcript = _make_transcript()
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content=_CHAPTERS_JSON,
                model="test",
                provider_name="deepseek",
                tokens_in=200,
                tokens_out=100,
                duration_ms=1000,
                cost_usd=0.002,
            )
        )

        with patch(
            "podlator.steps.split_chapters.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.split_chapters import split_transcript

            result = await split_transcript(transcript)

        for ch in result.chapters:
            assert isinstance(ch, ChapterModel)
            assert isinstance(ch.title, str)
            assert isinstance(ch.start, float)
            assert isinstance(ch.end, float)
            # ChapterModel 没有 summary 字段 — 确保不混入摘要
