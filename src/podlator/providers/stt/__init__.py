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
    raise ConfigError(f"Unknown STT provider: {settings.stt_provider}")
