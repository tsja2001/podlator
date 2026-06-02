"""Unit tests for douyin pipeline (mock LLM)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from podlator.providers.llm.base import LLMResult

_SAMPLE_SRT = """1
00:00:00,000 --> 00:00:05,000
Welcome to this interview about AI and the future.

2
00:00:05,000 --> 00:00:10,000
Today we have a special guest who has worked on many interesting projects.

3
00:00:10,000 --> 00:00:15,000
Let's start with the big picture question about technology.
"""

_MOCK_SPEAKER_JSON = json.dumps(
    [
        {"index": 0, "speaker": "HOST"},
        {"index": 1, "speaker": "HOST"},
        {"index": 2, "speaker": "HOST"},
    ]
)

_MOCK_SCRIPT = """# AI 与未来：一场深度对话

"我们今天聊的东西，可能五年后回头看会觉得特别幼稚。"

这是这次访谈最让我印象深刻的一句话。"""


class TestPipelineDouyin:
    """pipeline-douyin 命令的单元测试。"""

    @pytest.mark.asyncio
    async def test_srt_to_douyin_script_mock(self) -> None:
        """正常路径：SRT → Transcript → assign-speakers → douyin-script → .md。

        全程 mock LLM，验证各步骤串联正确。
        """
        # ── 准备 mock LLM ──
        call_count = [0]

        async def mock_complete(
            prompt, system=None, temperature=0.3, max_tokens=8192, **kwargs
        ):
            call_count[0] += 1
            if "assign speaker" in system.lower() if system else False:
                return LLMResult(
                    content=_MOCK_SPEAKER_JSON,
                    model="test",
                    provider_name="deepseek",
                    tokens_in=100,
                    tokens_out=50,
                    duration_ms=500,
                    cost_usd=0.001,
                )
            else:
                return LLMResult(
                    content=_MOCK_SCRIPT,
                    model="test",
                    provider_name="claude",
                    tokens_in=500,
                    tokens_out=300,
                    duration_ms=2000,
                    cost_usd=0.01,
                )

        # ── Mock: assign_speakers LLM 和 douyin_script LLM 都 mock ──
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(side_effect=mock_complete)

        with (
            patch(
                "podlator.steps.assign_speakers.get_llm_provider",
                return_value=mock_llm,
            ),
            patch(
                "podlator.steps.douyin_script.get_llm_provider",
                return_value=mock_llm,
            ),
        ):
            # Step 1: parse SRT
            import tempfile

            from podlator.steps.assign_speakers import assign_speakers
            from podlator.steps.douyin_script import generate_douyin_script
            from podlator.steps.parse_srt import parse_srt_file

            tmpdir = tempfile.mkdtemp()
            srt_path = __import__("pathlib").Path(tmpdir) / "test.srt"
            srt_path.write_text(_SAMPLE_SRT, encoding="utf-8")

            doc = parse_srt_file(srt_path, title="Test Interview")
            assert len(doc.segments) == 3

            # Step 2: assign speakers
            doc_with_speakers = await assign_speakers(doc, provider_name="deepseek")
            assert doc_with_speakers.segments[0].speaker is not None

            # Step 3: generate douyin script
            script = await generate_douyin_script(
                doc_with_speakers, provider_name="claude"
            )
            assert isinstance(script, str)
            assert len(script) > 0

            # Cleanup
            srt_path.unlink()
            __import__("os").rmdir(tmpdir)

    @pytest.mark.asyncio
    async def test_pipeline_handles_parse_failure(self) -> None:
        """失败路径：SRT 文件不存在时 parse-srt 抛出 FileNotFoundError。"""
        from podlator.steps.parse_srt import parse_srt_file

        with pytest.raises(FileNotFoundError, match="SRT 文件不存在"):
            parse_srt_file(__import__("pathlib").Path("/nonexistent/file.srt"))

    @pytest.mark.asyncio
    async def test_pipeline_handles_empty_srt(self) -> None:
        """边界条件：空 SRT 文件抛出 ValueError。"""
        import tempfile
        from pathlib import Path

        tmpdir = tempfile.mkdtemp()
        srt_path = Path(tmpdir) / "empty.srt"
        srt_path.write_text("", encoding="utf-8")

        from podlator.steps.parse_srt import parse_srt_file

        with pytest.raises(ValueError, match="SRT 文件为空"):
            parse_srt_file(srt_path)

        srt_path.unlink()
        __import__("os").rmdir(tmpdir)
