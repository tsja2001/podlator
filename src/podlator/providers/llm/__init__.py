"""LLM Provider 模块。"""

from __future__ import annotations

from podlator.config import Settings
from podlator.errors import ConfigError
from podlator.providers.llm.base import LLMProvider


def get_llm_provider(provider_name: str, settings: Settings) -> LLMProvider:
    """根据名称返回 LLM Provider 实例。"""
    if provider_name == "deepseek":
        from podlator.providers.llm.deepseek import DeepSeekProvider

        return DeepSeekProvider(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
            max_tokens=settings.deepseek_max_tokens,
        )
    if provider_name == "claude":
        from podlator.providers.llm.claude import ClaudeProvider

        return ClaudeProvider(
            api_key=settings.claude_api_key,
            base_url=settings.claude_base_url,
            model=settings.claude_model,
            max_tokens=settings.claude_max_tokens,
        )
    if provider_name in ("claude_cli", "codex_cli"):
        from podlator.providers.llm.cli_tool import CLIToolProvider

        backend = "claude" if provider_name == "claude_cli" else "codex"
        return CLIToolProvider(settings, backend=backend)

    raise ConfigError(f"Unknown LLM provider: {provider_name}")
