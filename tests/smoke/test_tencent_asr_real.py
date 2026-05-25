"""腾讯云 ASR + COS Smoke 测试，需要真实腾讯云配置。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from podlator.config import Settings
from podlator.providers.stt.tencent_cloud import TencentCloudProvider
from podlator.storage.cos_audio import TencentCosAudioStorage

pytestmark = pytest.mark.skipif(
    not os.getenv("PODLATOR_RUN_SMOKE"),
    reason="Smoke tests disabled (set PODLATOR_RUN_SMOKE=1)",
)

TEST_AUDIO_PATH = Path(
    "/Users/mac/Project_Personal/podlator/data/audio/"
    "2d31b656-82f7-4591-a1b6-306baa92306d/audio.mp3"
)


def _get_provider() -> TencentCloudProvider:
    settings = Settings()
    required = {
        "TENCENT_SECRET_ID": settings.tencent_secret_id,
        "TENCENT_SECRET_KEY": settings.tencent_secret_key,
        "TENCENT_COS_BUCKET": settings.tencent_cos_bucket,
        "TENCENT_COS_REGION": settings.tencent_cos_region,
        "TENCENT_COS_SECRET_ID": settings.tencent_cos_secret_id,
        "TENCENT_COS_SECRET_KEY": settings.tencent_cos_secret_key,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        pytest.skip(f"Tencent smoke config missing: {', '.join(missing)}")

    return TencentCloudProvider(
        secret_id=settings.tencent_secret_id,
        secret_key=settings.tencent_secret_key,
        region=settings.tencent_asr_region,
        engine_model_type=settings.tencent_asr_engine_model_type,
        res_text_format=settings.tencent_asr_res_text_format,
        speaker_diarization=settings.tencent_asr_speaker_diarization,
        poll_interval_seconds=settings.tencent_asr_poll_interval_seconds,
        timeout_seconds=settings.tencent_asr_timeout_seconds,
        cos_storage=TencentCosAudioStorage(
            bucket=settings.tencent_cos_bucket,
            region=settings.tencent_cos_region,
            secret_id=settings.tencent_cos_secret_id,
            secret_key=settings.tencent_cos_secret_key,
            token=settings.tencent_cos_token,
            prefix=settings.tencent_cos_prefix,
            scheme=settings.tencent_cos_scheme,
            presigned_expires_seconds=settings.tencent_cos_presigned_expires_seconds,
            delete_after_transcribe=settings.tencent_cos_delete_after_transcribe,
        ),
    )


@pytest.mark.asyncio
async def test_tencent_asr_transcribe_real() -> None:
    """通过 COS URL 路径调用真实腾讯云 ASR。"""
    if not TEST_AUDIO_PATH.exists():
        pytest.skip(f"Test audio file not found: {TEST_AUDIO_PATH}")

    provider = _get_provider()
    result = await provider.transcribe(TEST_AUDIO_PATH, diarize=False)

    assert result.provider_name == "tencent_cloud"
    assert result.segments
    assert result.full_text
    assert result.cost_usd == 0.0
