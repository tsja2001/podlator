"""Unit tests for douyin_script step (mock LLM)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from podlator.providers.llm.base import LLMResult
from podlator.steps.models import (
    TranscriptDocument,
    TranscriptProviderMeta,
    TranscriptSegmentModel,
    TranscriptSource,
)

# Mock LLM 返回的抖音解说稿
_MOCK_SCRIPT = """# 黄仁勋被问到"上头"：一场关于英伟达护城河的深度交锋

你这种输家心态我不能接受。

就在不久前，硅谷最火的一档科技播客的录影棚里，黄仁勋，这个掌管着全球市值第一公司的男人，突然把声音抬高了。"""


def _make_transcript(n: int = 10, with_speakers: bool = True) -> TranscriptDocument:
    """创建测试用 TranscriptDocument。"""
    segments = []
    for i in range(n):
        spk = (
            "HOST"
            if (with_speakers and i % 2 == 0)
            else ("GUEST" if with_speakers else None)
        )
        segments.append(
            TranscriptSegmentModel(
                index=i,
                start=i * 30.0,
                end=(i + 1) * 30.0,
                text=f"This is segment {i} of the interview transcript. "
                f"Here we discuss important topics about technology and AI.",
                speaker=spk,
            )
        )
    return TranscriptDocument(
        source=TranscriptSource(
            title="Test Interview",
            duration_seconds=n * 30.0,
        ),
        provider=TranscriptProviderMeta(name="srt"),
        text=" ".join(s.text for s in segments),
        segments=segments,
    )


class TestDouyinScript:
    """douyin-script step 的单元测试。"""

    @pytest.mark.asyncio
    async def test_generates_douyin_script(self) -> None:
        """正常路径：LLM 返回解说稿，函数返回 Markdown 字符串。"""
        transcript = _make_transcript(20)

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content=_MOCK_SCRIPT,
                model="test-model",
                provider_name="claude",
                tokens_in=2000,
                tokens_out=1500,
                duration_ms=5000,
                cost_usd=0.05,
            )
        )

        with patch(
            "podlator.steps.douyin_script.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.douyin_script import generate_douyin_script

            result = await generate_douyin_script(transcript, provider_name="claude")

        assert isinstance(result, str)
        assert len(result) > 0
        assert "黄仁勋" in result
        mock_llm.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_respects_max_input_chars(self) -> None:
        """边界条件：内容过长时自动截断到 max_input_chars。"""
        transcript = _make_transcript(500)  # 很多 segments

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content=_MOCK_SCRIPT,
                model="test",
                provider_name="claude",
                tokens_in=5000,
                tokens_out=1500,
                duration_ms=3000,
                cost_usd=0.05,
            )
        )

        with patch(
            "podlator.steps.douyin_script.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.douyin_script import generate_douyin_script

            result = await generate_douyin_script(
                transcript,
                provider_name="claude",
                max_input_chars=3000,
            )

        # 应该被调用了，传入了不超过 max_input_chars 的内容
        call_args = mock_llm.complete.call_args
        prompt = call_args[0][0] if call_args[0] else call_args.kwargs.get("prompt", "")
        assert len(prompt) <= 3500  # 允许一些余量（模板本身有些字符）
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_empty_segments_raises(self) -> None:
        """失败路径：空 segments 抛出 ValueError。"""
        transcript = TranscriptDocument(
            source=TranscriptSource(title="Empty"),
            provider=TranscriptProviderMeta(name="srt"),
        )

        from podlator.steps.douyin_script import generate_douyin_script

        with pytest.raises(ValueError, match="segments 为空"):
            await generate_douyin_script(transcript)

    @pytest.mark.asyncio
    async def test_llm_failure_raises(self) -> None:
        """失败路径：LLM 调用失败时抛出异常。"""
        transcript = _make_transcript(10)

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(side_effect=RuntimeError("API connection failed"))

        with patch(
            "podlator.steps.douyin_script.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.douyin_script import generate_douyin_script

            with pytest.raises(RuntimeError, match="API connection failed"):
                await generate_douyin_script(transcript, provider_name="claude")

    @pytest.mark.asyncio
    async def test_includes_speaker_info_in_prompt(self) -> None:
        """验证 prompt 中包含说话人标注信息。"""
        transcript = _make_transcript(5)

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content=_MOCK_SCRIPT,
                model="test",
                provider_name="claude",
                tokens_in=500,
                tokens_out=300,
                duration_ms=2000,
                cost_usd=0.02,
            )
        )

        with patch(
            "podlator.steps.douyin_script.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.douyin_script import generate_douyin_script

            await generate_douyin_script(transcript, provider_name="claude")

        call_args = mock_llm.complete.call_args
        prompt = call_args[0][0] if call_args[0] else call_args.kwargs.get("prompt", "")
        assert "HOST" in prompt, "Prompt should include speaker labels"

    @pytest.mark.asyncio
    async def test_no_speakers_handled_gracefully(self) -> None:
        """边界条件：没有说话人标注的 transcript 也能正常处理。"""
        transcript = _make_transcript(5, with_speakers=False)

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content=_MOCK_SCRIPT,
                model="test",
                provider_name="claude",
                tokens_in=300,
                tokens_out=200,
                duration_ms=1500,
                cost_usd=0.01,
            )
        )

        with patch(
            "podlator.steps.douyin_script.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.douyin_script import generate_douyin_script

            result = await generate_douyin_script(transcript)

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_passes_custom_title_to_prompt(self) -> None:
        """验证自定义标题会出现在 prompt 中。"""
        transcript = _make_transcript(5)
        custom_title = "Custom Interview Title"

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content=_MOCK_SCRIPT,
                model="test",
                provider_name="claude",
                tokens_in=300,
                tokens_out=200,
                duration_ms=1500,
                cost_usd=0.01,
            )
        )

        with patch(
            "podlator.steps.douyin_script.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.douyin_script import generate_douyin_script

            await generate_douyin_script(transcript, title=custom_title)

        call_args = mock_llm.complete.call_args
        prompt = call_args[0][0] if call_args[0] else call_args.kwargs.get("prompt", "")
        assert custom_title in prompt
