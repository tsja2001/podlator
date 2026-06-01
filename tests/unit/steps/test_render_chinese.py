"""Unit tests for render_chinese step (mock LLM)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from podlator.providers.llm.base import LLMResult
from podlator.steps.models import (
    ChapterDocument,
    ChapterModel,
    TranscriptDocument,
    TranscriptProviderMeta,
    TranscriptSegmentModel,
    TranscriptSource,
)


def _make_transcript() -> TranscriptDocument:
    segments = [
        TranscriptSegmentModel(
            index=i,
            start=i * 10.0,
            end=(i + 1) * 10.0,
            text=f"Segment {i} text.",
            speaker=f"SPEAKER_{i % 2}",
        )
        for i in range(4)
    ]
    return TranscriptDocument(
        source=TranscriptSource(title="Test Episode", duration_seconds=40.0),
        provider=TranscriptProviderMeta(name="deepgram"),
        text=" ".join(s.text for s in segments),
        segments=segments,
    )


def _make_chapters() -> ChapterDocument:
    return ChapterDocument(
        chapters=[
            ChapterModel(
                index=0,
                title="开场",
                start=0.0,
                end=20.0,
                segment_indices=[0, 1],
            ),
            ChapterModel(
                index=1,
                title="正文",
                start=20.0,
                end=40.0,
                segment_indices=[2, 3],
            ),
        ]
    )


def _make_llm_result(content: str) -> LLMResult:
    return LLMResult(
        content=content,
        model="test",
        provider_name="deepseek",
        tokens_in=200,
        tokens_out=100,
        duration_ms=500,
        cost_usd=0.001,
    )


class TestRenderChinese:
    @pytest.mark.asyncio
    async def test_render_summary_mode(self) -> None:
        """验证 summary 模式能正常生成 Markdown。"""
        transcript = _make_transcript()
        chapters = _make_chapters()
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=_make_llm_result("## 开场\n\n这是开场内容。")
        )

        with patch(
            "podlator.steps.render_chinese.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.render_chinese import render_chinese

            result = await render_chinese(
                transcript, chapters, mode="summary", provider_name="deepseek"
            )

        assert "Test Episode" in result
        assert "开场" in result
        assert "正文" in result

    @pytest.mark.asyncio
    async def test_render_full_mode(self) -> None:
        """验证 full 模式能正常生成 Markdown（全文翻译）。"""
        transcript = _make_transcript()
        chapters = _make_chapters()
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=_make_llm_result("## 开场\n\n第一段的完整翻译。")
        )

        with patch(
            "podlator.steps.render_chinese.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.render_chinese import render_chinese

            result = await render_chinese(
                transcript, chapters, mode="full", provider_name="deepseek"
            )

        assert "Test Episode" in result
        assert "中文全文翻译" in result

    @pytest.mark.asyncio
    async def test_summary_and_full_different_modes(self) -> None:
        """验证 summary 和 full 模式行为不同（prompt 不同导致不同标签）。"""
        transcript = _make_transcript()
        chapters = _make_chapters()
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value=_make_llm_result("翻译内容。"))

        with patch(
            "podlator.steps.render_chinese.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.render_chinese import render_chinese

            summary_result = await render_chinese(transcript, chapters, mode="summary")
            full_result = await render_chinese(transcript, chapters, mode="full")

        assert "精简摘要" in summary_result
        assert "全文翻译" in full_result

    @pytest.mark.asyncio
    async def test_empty_chapters_raises(self) -> None:
        """空章节列表抛出 ValueError。"""
        transcript = _make_transcript()
        chapters = ChapterDocument(chapters=[])

        from podlator.steps.render_chinese import render_chinese

        with pytest.raises(ValueError, match="Chapters 为空"):
            await render_chinese(transcript, chapters)

    @pytest.mark.asyncio
    async def test_partial_chapter_failure(self) -> None:
        """某一章节渲染失败时，其他章节继续渲染。"""
        transcript = _make_transcript()
        # 3 chapters, 2nd one triggers error
        chapters = ChapterDocument(
            chapters=[
                ChapterModel(
                    index=0,
                    title="Ch1",
                    start=0.0,
                    end=10.0,
                    segment_indices=[0],
                ),
                ChapterModel(
                    index=1,
                    title="Ch2",
                    start=10.0,
                    end=20.0,
                    segment_indices=[1],
                ),
                ChapterModel(
                    index=2,
                    title="Ch3",
                    start=20.0,
                    end=40.0,
                    segment_indices=[2, 3],
                ),
            ]
        )
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            side_effect=[
                _make_llm_result("Ch1 内容。"),
                Exception("Ch2 LLM error!"),
                _make_llm_result("Ch3 内容。"),
            ]
        )

        with patch(
            "podlator.steps.render_chinese.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.render_chinese import render_chinese

            result = await render_chinese(transcript, chapters)

        assert "Ch1 内容" in result
        assert "Ch3 内容" in result
        assert "章节渲染失败" in result
