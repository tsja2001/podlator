"""Settings 配置测试。"""

from __future__ import annotations

from podlator.config import Settings


def test_settings_defaults() -> None:
    """默认值正确。"""
    s = Settings()
    assert s.log_level == "INFO"
    assert s.api_port == 8000
    assert s.stt_provider == "deepgram"


def test_settings_env_override(monkeypatch) -> None:
    """环境变量可覆盖默认值。"""
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("API_PORT", "9000")
    s = Settings()
    assert s.log_level == "DEBUG"
    assert s.api_port == 9000
