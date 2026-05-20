"""transcribe 节点测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from podlator.errors import NodeError, ProviderError
from podlator.graph.nodes.transcribe import run
from podlator.graph.state import TranscriptSegment
from podlator.providers.stt.base import STTResult


@pytest.fixture
def state() -> dict:
    return {
        "task_id": "test-task",
        "audio_path": "/tmp/test.mp3",
    }


@pytest.fixture
def fake_segments() -> list[TranscriptSegment]:
    return [
        {
            "text": "Hello world",
            "start": 0.0,
            "end": 1.0,
            "speaker": "SPEAKER_0",
            "confidence": 0.99,
        },
    ]


@pytest.fixture
def fake_result(fake_segments: list[TranscriptSegment]) -> STTResult:
    return STTResult(
        segments=fake_segments,
        full_text="Hello world",
        has_diarization=True,
        provider_name="deepgram",
        duration_ms=500.0,
        cost_usd=0.01,
    )


@pytest.mark.asyncio
async def test_transcribe_success(state: dict, fake_result: STTResult) -> None:
    """正常转写，返回 transcript_segments 等字段。"""
    mock_stt = AsyncMock()
    mock_stt.transcribe.return_value = fake_result

    with patch(
        "podlator.graph.nodes.transcribe.get_stt_provider",
        return_value=mock_stt,
    ):
        result = await run(state)

    assert result["transcript_text"] == "Hello world"
    assert len(result["transcript_segments"]) == 1
    assert result["stt_provider"] == "deepgram"
    assert result["has_diarization"] is True


@pytest.mark.asyncio
async def test_transcribe_provider_error(state: dict) -> None:
    """Provider 失败抛出 NodeError。"""
    mock_stt = AsyncMock()
    mock_stt.transcribe.side_effect = ProviderError(
        "deepgram", "API error", retryable=True
    )

    with patch(
        "podlator.graph.nodes.transcribe.get_stt_provider",
        return_value=mock_stt,
    ):
        with pytest.raises(NodeError, match=r"\[transcribe\]"):
            await run(state)


@pytest.mark.asyncio
async def test_transcribe_missing_audio_path() -> None:
    """缺少 audio_path 返回空。"""
    result = await run({"task_id": "no-audio"})
    assert result == {} or "transcript_text" not in result
