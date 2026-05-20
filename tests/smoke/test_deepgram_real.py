"""Deepgram STT Smoke 测试 — 需要真实 API Key。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from podlator.config import Settings
from podlator.providers.stt.deepgram import DeepgramProvider

pytestmark = pytest.mark.skipif(
    not os.getenv("PODLATOR_RUN_SMOKE"),
    reason="Smoke tests disabled (set PODLATOR_RUN_SMOKE=1)",
)


def _get_provider() -> DeepgramProvider:
    settings = Settings()
    if not settings.deepgram_api_key:
        pytest.skip("DEEPGRAM_API_KEY not configured")
    return DeepgramProvider(
        api_key=settings.deepgram_api_key,
        model=settings.deepgram_model,
    )


@pytest.mark.asyncio
async def test_deepgram_transcribe_real() -> None:
    """真实 API 转写短音频。"""
    provider = _get_provider()
    audio_path = Path("tests/fixtures/audio/sample_30s.mp3")
    if not audio_path.exists():
        pytest.skip(f"Test audio file not found: {audio_path}")

    result = await provider.transcribe(audio_path, diarize=False)
    assert len(result.segments) > 0
    assert result.full_text
    assert result.cost_usd > 0
