"""Unit tests for assign_speakers step (mock LLM)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from podlator.providers.llm.base import LLMResult
from podlator.steps.models import (
    TranscriptDocument,
    TranscriptProviderMeta,
    TranscriptSegmentModel,
    TranscriptSource,
)

_SPEAKER_JSON = json.dumps(
    [
        {"index": 0, "speaker": "HOST"},
        {"index": 1, "speaker": "GUEST"},
        {"index": 2, "speaker": "HOST"},
    ]
)


def _make_transcript(speakers: list[str | None] | None = None) -> TranscriptDocument:
    """创建测试用 TranscriptDocument。"""
    if speakers is None:
        speakers = [None, None, None]

    segments = [
        TranscriptSegmentModel(
            index=i,
            start=i * 10.0,
            end=(i + 1) * 10.0,
            text=f"Speaker says something {i}.",
            speaker=spk,
        )
        for i, spk in enumerate(speakers)
    ]
    return TranscriptDocument(
        source=TranscriptSource(title="Test"),
        provider=TranscriptProviderMeta(name="srt"),
        text=" ".join(s.text for s in segments),
        segments=segments,
    )


class TestAssignSpeakers:
    @pytest.mark.asyncio
    async def test_assigns_speakers_from_llm(self) -> None:
        """正常路径：LLM 返回说话人标签，正确写回 segments。"""
        transcript = _make_transcript()
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content=_SPEAKER_JSON,
                model="test",
                provider_name="deepseek",
                tokens_in=100,
                tokens_out=50,
                duration_ms=500,
                cost_usd=0.001,
            )
        )

        with patch(
            "podlator.steps.assign_speakers.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.assign_speakers import assign_speakers

            result = await assign_speakers(transcript, provider_name="deepseek")

        assert result.segments[0].speaker == "HOST"
        assert result.segments[1].speaker == "GUEST"
        assert result.segments[2].speaker == "HOST"

    @pytest.mark.asyncio
    async def test_does_not_modify_text_or_timestamps(self) -> None:
        """验证 assign_speakers 只修改 speaker 字段，不改正文和时间戳。"""
        transcript = _make_transcript()
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content=_SPEAKER_JSON,
                model="test",
                provider_name="deepseek",
                tokens_in=100,
                tokens_out=50,
                duration_ms=500,
                cost_usd=0.001,
            )
        )

        with patch(
            "podlator.steps.assign_speakers.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.assign_speakers import assign_speakers

            result = await assign_speakers(transcript)

        for i, seg in enumerate(result.segments):
            orig = transcript.segments[i]
            assert seg.text == orig.text, f"Segment {i} text modified"
            assert seg.start == orig.start, f"Segment {i} start modified"
            assert seg.end == orig.end, f"Segment {i} end modified"

    @pytest.mark.asyncio
    async def test_empty_segments_returns_unchanged(self) -> None:
        """空 segments 时直接返回原 transcript。"""
        transcript = TranscriptDocument(
            source=TranscriptSource(title="Empty"),
            provider=TranscriptProviderMeta(name="srt"),
        )

        from podlator.steps.assign_speakers import assign_speakers

        result = await assign_speakers(transcript)
        assert result.segments == []

    @pytest.mark.asyncio
    async def test_llm_returns_invalid_json(self) -> None:
        """LLM 返回非法 JSON 时保持原 transcript 不变。"""
        transcript = _make_transcript()
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content="not valid json!!!",
                model="test",
                provider_name="deepseek",
                tokens_in=100,
                tokens_out=50,
                duration_ms=500,
                cost_usd=0.001,
            )
        )

        with patch(
            "podlator.steps.assign_speakers.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.assign_speakers import assign_speakers

            result = await assign_speakers(transcript)

        # speaker 应该保持原样（全部 None）
        for seg in result.segments:
            assert seg.speaker is None

    @pytest.mark.asyncio
    async def test_partial_indices_in_llm_response(self) -> None:
        """LLM 只返回部分 index 时，缺失的保持原样。"""
        transcript = _make_transcript()
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content='[{"index": 0, "speaker": "HOST"}]',
                model="test",
                provider_name="deepseek",
                tokens_in=100,
                tokens_out=50,
                duration_ms=500,
                cost_usd=0.001,
            )
        )

        with patch(
            "podlator.steps.assign_speakers.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.assign_speakers import assign_speakers

            result = await assign_speakers(transcript)

        assert result.segments[0].speaker == "HOST"
        # index 1, 2 未在 LLM 响应中，保持 None
        assert result.segments[1].speaker is None
        assert result.segments[2].speaker is None

    @pytest.mark.asyncio
    async def test_llm_returns_code_fenced_json(self) -> None:
        """LLM 返回 ```json ... ``` 包裹的 JSON 时能正确解析。"""
        transcript = _make_transcript()
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content="```json\n" + _SPEAKER_JSON + "\n```",
                model="test",
                provider_name="deepseek",
                tokens_in=100,
                tokens_out=50,
                duration_ms=500,
                cost_usd=0.001,
            )
        )

        with patch(
            "podlator.steps.assign_speakers.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.assign_speakers import assign_speakers

            result = await assign_speakers(transcript)

        assert result.segments[0].speaker == "HOST"
        assert result.segments[1].speaker == "GUEST"
