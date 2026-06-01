"""transcribe 节点测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from podlator.errors import NodeError
from podlator.graph.nodes.transcribe import run
from podlator.steps.models import (
    TranscriptDocument,
    TranscriptProviderMeta,
    TranscriptSegmentModel,
    TranscriptSource,
)


@pytest.fixture
def state() -> dict:
    return {
        "task_id": "test-task",
        "audio_path": "/tmp/test.mp3",
    }


def _fake_doc() -> TranscriptDocument:
    return TranscriptDocument(
        source=TranscriptSource(audio_path="/tmp/test.mp3", duration_seconds=10.0),
        provider=TranscriptProviderMeta(name="tencent_cloud", cost_usd=0.01),
        text="Hello world",
        segments=[
            TranscriptSegmentModel(
                index=0,
                start=0.0,
                end=1.0,
                text="Hello world",
                speaker="SPEAKER_0",
                confidence=0.99,
            ),
        ],
    )


@pytest.mark.asyncio
async def test_transcribe_success(state: dict) -> None:
    """正常转写，通过 step 层获取结果并映射到 state。"""
    with patch(
        "podlator.graph.nodes.transcribe.transcribe_audio",
        new_callable=AsyncMock,
        return_value=_fake_doc(),
    ):
        result = await run(state)

    assert result["transcript_text"] == "Hello world"
    assert len(result["transcript_segments"]) == 1
    assert result["stt_provider"] == "tencent_cloud"
    assert result["total_cost_usd"] == 0.01


@pytest.mark.asyncio
async def test_transcribe_provider_error(state: dict) -> None:
    """step 抛异常时 @node 装饰器包装为 NodeError。"""
    with patch(
        "podlator.graph.nodes.transcribe.transcribe_audio",
        new_callable=AsyncMock,
        side_effect=RuntimeError("speech-transcriber failed"),
    ):
        with pytest.raises(NodeError, match=r"\[transcribe\]"):
            await run(state)


@pytest.mark.asyncio
async def test_transcribe_missing_audio_path() -> None:
    """缺少 audio_path 返回空。"""
    result = await run({"task_id": "no-audio"})
    assert result == {} or "transcript_text" not in result
