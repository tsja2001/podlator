"""Provider 工厂函数测试。"""

from __future__ import annotations

import pytest

from podlator.config import Settings
from podlator.errors import ConfigError
from podlator.providers.downloader import get_downloader
from podlator.providers.downloader.ytdlp import YtDlpDownloader
from podlator.providers.llm import get_llm_provider
from podlator.providers.stt import get_stt_provider


def test_get_downloader_returns_ytdlp() -> None:
    """get_downloader 返回 YtDlpDownloader。"""
    settings = Settings()
    dl = get_downloader(settings)
    assert isinstance(dl, YtDlpDownloader)


def test_get_stt_provider_deepgram(monkeypatch) -> None:
    """stt_provider=deepgram 返回 DeepgramProvider。"""
    settings = Settings()
    monkeypatch.setattr(settings, "stt_provider", "deepgram")
    monkeypatch.setattr(settings, "deepgram_api_key", "test-key")
    provider = get_stt_provider(settings)
    from podlator.providers.stt.deepgram import DeepgramProvider

    assert isinstance(provider, DeepgramProvider)


def test_get_stt_provider_unknown() -> None:
    """未知 STT provider 抛出 ConfigError。"""
    settings = Settings()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(settings, "stt_provider", "unknown")
    with pytest.raises(ConfigError, match="Unknown STT provider"):
        get_stt_provider(settings)
    monkeypatch.undo()


def test_get_llm_provider_deepseek() -> None:
    """provider_name=deepseek 返回 DeepSeekProvider。"""
    settings = Settings()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    provider = get_llm_provider("deepseek", settings)
    from podlator.providers.llm.deepseek import DeepSeekProvider

    assert isinstance(provider, DeepSeekProvider)
    monkeypatch.undo()


def test_get_llm_provider_claude() -> None:
    """provider_name=claude 返回 ClaudeProvider。"""
    settings = Settings()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(settings, "claude_api_key", "test-key")
    provider = get_llm_provider("claude", settings)
    from podlator.providers.llm.claude import ClaudeProvider

    assert isinstance(provider, ClaudeProvider)
    monkeypatch.undo()


def test_get_llm_provider_unknown() -> None:
    """未知 LLM provider 抛出 ConfigError。"""
    settings = Settings()
    with pytest.raises(ConfigError, match="Unknown LLM provider"):
        get_llm_provider("unknown", settings)
