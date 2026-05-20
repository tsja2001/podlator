"""LLM Smoke 测试 — 需要真实 API Key。"""

from __future__ import annotations

import os

import pytest

from podlator.config import Settings
from podlator.providers.llm.claude import ClaudeProvider
from podlator.providers.llm.deepseek import DeepSeekProvider

pytestmark = pytest.mark.skipif(
    not os.getenv("PODLATOR_RUN_SMOKE"),
    reason="Smoke tests disabled (set PODLATOR_RUN_SMOKE=1)",
)


def _get_deepseek() -> DeepSeekProvider:
    settings = Settings()
    if not settings.deepseek_api_key:
        pytest.skip("DEEPSEEK_API_KEY not configured")
    return DeepSeekProvider(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
        max_tokens=settings.deepseek_max_tokens,
    )


def _get_claude() -> ClaudeProvider:
    settings = Settings()
    if not settings.claude_api_key:
        pytest.skip("CLAUDE_API_KEY not configured")
    return ClaudeProvider(
        api_key=settings.claude_api_key,
        base_url=settings.claude_base_url,
        model=settings.claude_model,
        max_tokens=settings.claude_max_tokens,
    )


@pytest.mark.asyncio
async def test_deepseek_real() -> None:
    """真实调用 DeepSeek API。"""
    provider = _get_deepseek()
    result = await provider.complete("用一句话描述什么是播客。")
    assert result.content
    assert result.tokens_in > 0
    assert result.cost_usd >= 0


@pytest.mark.asyncio
async def test_claude_real() -> None:
    """真实调用 Claude API（第三方平台）。"""
    provider = _get_claude()
    result = await provider.complete("用一句话描述什么是播客。")
    assert result.content
