"""Unit tests for polish step (mock LLM)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from podlator.providers.llm.base import LLMResult


def _make_llm_result(content: str) -> LLMResult:
    return LLMResult(
        content=content,
        model="test",
        provider_name="claude",
        tokens_in=500,
        tokens_out=200,
        duration_ms=1000,
        cost_usd=0.005,
    )


class TestPolishMarkdown:
    @pytest.mark.asyncio
    async def test_polish_returns_content(self) -> None:
        """正常路径：LLM 返回润色后的 Markdown。"""
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=_make_llm_result("# 润色后的标题\n\n润色后的内容。")
        )

        with patch(
            "podlator.steps.polish.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.polish import polish_markdown

            result = await polish_markdown(
                "# 原始标题\n\n原始内容。",
                title="Test Episode",
                provider_name="claude",
            )

        assert "润色后的标题" in result
        assert "润色后的内容" in result

    @pytest.mark.asyncio
    async def test_polish_without_title(self) -> None:
        """不传 title 时也能正常运行。"""
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value=_make_llm_result("# 润色内容"))

        with patch(
            "podlator.steps.polish.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.polish import polish_markdown

            result = await polish_markdown("# 原始", provider_name="claude")

        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_polish_uses_deepseek_provider(self) -> None:
        """验证可以使用 deepseek provider。"""
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value=_make_llm_result("# DeepSeek 润色"))

        with patch(
            "podlator.steps.polish.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.polish import polish_markdown

            result = await polish_markdown("# Original", provider_name="deepseek")

        assert "DeepSeek 润色" in result
