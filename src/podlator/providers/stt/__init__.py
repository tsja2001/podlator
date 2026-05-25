"""STT Provider 模块。"""

from __future__ import annotations

from podlator.config import Settings
from podlator.errors import ConfigError
from podlator.providers.stt.base import STTProvider


def get_stt_provider(settings: Settings) -> STTProvider:
    """根据配置返回 STT Provider 实例。"""
    if settings.stt_provider == "deepgram":
        from podlator.providers.stt.deepgram import DeepgramProvider

        return DeepgramProvider(
            api_key=settings.deepgram_api_key, model=settings.deepgram_model
        )
    if settings.stt_provider == "tencent_cloud":
        from podlator.providers.stt.tencent_cloud import TencentCloudProvider
        from podlator.storage.cos_audio import TencentCosAudioStorage

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
    raise ConfigError(f"Unknown STT provider: {settings.stt_provider}")
