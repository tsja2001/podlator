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


def test_settings_claude_model_env_override(monkeypatch) -> None:
    """CLAUDE_MODEL 可覆盖 Claude 的模型名。"""
    monkeypatch.setenv("CLAUDE_MODEL", "claude-opus-custom")
    s = Settings()
    assert s.claude_model == "claude-opus-custom"


def test_deepseek_max_tokens_default_is_32768() -> None:
    """DeepSeek max_tokens 类默认值应为 32768（M5.0 从 8192 上调）。"""
    assert Settings.model_fields["deepseek_max_tokens"].default == 32768


def test_claude_max_tokens_default_is_8192() -> None:
    """Claude max_tokens 类默认值应为 8192（M5.0 从 4096 上调）。"""
    assert Settings.model_fields["claude_max_tokens"].default == 8192
