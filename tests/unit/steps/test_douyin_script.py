"""Unit tests for douyin_script step (mock LLM).

覆盖：
- 单段式 (simple=True)：原有行为，一次 LLM 调用
- 两段式 (simple=False，默认)：blueprint + finalize + 可选补足回路
- 边界条件：空 segments、超长截断、无说话人
- 失败路径：LLM 失败、降级
"""

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

# ── 测试数据 ──

# 短 mock 脚本（用于测试，约 90 中文字符）
_MOCK_SHORT_SCRIPT = """# 黄仁勋被问到"上头"

你这种输家心态我不能接受。

就在不久前，硅谷最火的一档科技播客里，黄仁勋，这个掌管着全球市值第一公司的男人，突然把声音抬高了。"""

# 长 mock 脚本（约 6000 中文字符，用于跳过补足回路）
_MOCK_LONG_SCRIPT = (
    "黄仁勋最近在一档硅谷播客里被问到了护城河的问题。"
    "这个问题其实问了很多年了，英伟达到底有没有护城河？"
    "你看，市场上一直有人觉得，只要砸钱堆人做芯片，总能追上英伟达。"
    "但说实话，这种思维方式恰恰忽略了英伟达最核心的竞争力——"
    "不是硬件，是生态。黄仁勋自己怎么说呢？他说，英伟达的护城河"
    "不在于某一款芯片有多强，而在于整个 CUDA 生态有超过四百万开发者，"
    "这个网络效应是任何竞争对手都无法复制的。你想想，四百万开发者意味着什么？"
    "意味着几乎所有 AI 框架、库、工具链，都是先在 CUDA 上跑的。"
    "这不是技术问题，是时间问题。黄仁勋这个人很有意思，"
    "他是那种越被质疑越兴奋的类型。当主持人追问谷歌微软自己造芯片怎么办时，"
    "他不急不躁，反而笑着说'他们一直在造啊'。这句话背后的自信来自于"
    "他对行业的深刻理解——造芯片不难，造生态才难。"
    "英伟达花了将近二十年建立开发者关系、软件栈、合作伙伴网络，"
    "不是一朝一夕能被替代的。更关键的是，英伟达现在从两年一代加速到一年一代，"
    "从芯片到系统到软件全栈自研。这意味着追赶者不是在追静止目标，"
    "而是在追加速跑的人。等你好不容易追上 H100，Blackwell 已经量产了，"
    "等你终于对标 Blackwell，Rubin 又快发布了。这就是'跑步机效应'——"
    "你在跑步机上拼命跑，但永远追不上前面的人，因为前面的也在加速。"
    # 重复多次以达到约 6000 字
) * 25


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


def _make_llm_result(content: str = "", **kwargs) -> LLMResult:
    """创建 LLMResult，合并默认值和自定义字段。"""
    defaults = {
        "content": content or _MOCK_SHORT_SCRIPT,
        "model": "test-model",
        "provider_name": "claude",
        "tokens_in": 2000,
        "tokens_out": 1500,
        "duration_ms": 5000,
        "cost_usd": 0.05,
    }
    defaults.update(kwargs)
    return LLMResult(**defaults)


# ── 单段式 (simple=True) 测试 — 保持向后兼容 ──


class TestDouyinScriptSimple:
    """单段式 (--simple) 的单元测试。"""

    @pytest.mark.asyncio
    async def test_generates_douyin_script_simple(self) -> None:
        """正常路径：simple 模式一次 LLM 调用产出解说稿。"""
        transcript = _make_transcript(20)

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value=_make_llm_result())

        with patch(
            "podlator.steps.douyin_script.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.douyin_script import generate_douyin_script

            result = await generate_douyin_script(
                transcript, provider_name="claude", simple=True
            )

        assert isinstance(result, str)
        assert len(result) > 0
        assert "黄仁勋" in result
        mock_llm.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_respects_max_input_chars(self) -> None:
        """边界条件：内容过长时自动截断到 max_input_chars。"""
        transcript = _make_transcript(500)

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value=_make_llm_result())

        with patch(
            "podlator.steps.douyin_script.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.douyin_script import generate_douyin_script

            result = await generate_douyin_script(
                transcript,
                provider_name="claude",
                max_input_chars=3000,
                simple=True,
            )

        call_args = mock_llm.complete.call_args
        prompt = call_args[0][0] if call_args[0] else call_args.kwargs.get("prompt", "")
        assert len(prompt) <= 3500
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
                await generate_douyin_script(
                    transcript, provider_name="claude", simple=True
                )

    @pytest.mark.asyncio
    async def test_includes_speaker_info_in_prompt(self) -> None:
        """验证 prompt 中包含说话人标注信息。"""
        transcript = _make_transcript(5)

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value=_make_llm_result())

        with patch(
            "podlator.steps.douyin_script.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.douyin_script import generate_douyin_script

            await generate_douyin_script(
                transcript, provider_name="claude", simple=True
            )

        call_args = mock_llm.complete.call_args
        prompt = call_args[0][0] if call_args[0] else call_args.kwargs.get("prompt", "")
        assert "HOST" in prompt, "Prompt should include speaker labels"

    @pytest.mark.asyncio
    async def test_no_speakers_handled_gracefully(self) -> None:
        """边界条件：没有说话人标注的 transcript 也能正常处理。"""
        transcript = _make_transcript(5, with_speakers=False)

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value=_make_llm_result())

        with patch(
            "podlator.steps.douyin_script.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.douyin_script import generate_douyin_script

            result = await generate_douyin_script(transcript, simple=True)

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_passes_custom_title_to_prompt(self) -> None:
        """验证自定义标题会出现在 prompt 中。"""
        transcript = _make_transcript(5)
        custom_title = "Custom Interview Title"

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value=_make_llm_result())

        with patch(
            "podlator.steps.douyin_script.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.douyin_script import generate_douyin_script

            await generate_douyin_script(transcript, title=custom_title, simple=True)

        call_args = mock_llm.complete.call_args
        prompt = call_args[0][0] if call_args[0] else call_args.kwargs.get("prompt", "")
        assert custom_title in prompt


# ── 两段式 (simple=False，默认) 测试 ──


class TestDouyinScriptTwoStage:
    """两段式生成的单元测试。"""

    @pytest.mark.asyncio
    async def test_two_stage_calls_both_providers(self) -> None:
        """两段式：blueprint + finalize 分别调用 provider。"""
        transcript = _make_transcript(20)

        mock_llm = AsyncMock()
        # 返回长脚本避免触发补足回路
        mock_llm.complete = AsyncMock(
            return_value=_make_llm_result(content=_MOCK_LONG_SCRIPT)
        )

        with patch(
            "podlator.steps.douyin_script.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.douyin_script import generate_douyin_script

            result = await generate_douyin_script(
                transcript,
                blueprint_provider="deepseek",
                finalize_provider="claude",
            )

        assert isinstance(result, str)
        assert len(result) > 0
        # 两段式至少调用 2 次（blueprint + finalize）
        assert mock_llm.complete.call_count >= 2

    @pytest.mark.asyncio
    async def test_simple_mode_still_works(self) -> None:
        """simple=True 保留原始单段式行为。"""
        transcript = _make_transcript(5)

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value=_make_llm_result())

        with patch(
            "podlator.steps.douyin_script.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.douyin_script import generate_douyin_script

            result = await generate_douyin_script(
                transcript, provider_name="claude", simple=True
            )

        assert isinstance(result, str)
        mock_llm.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_supplement_loop_triggers_when_short(self) -> None:
        """字数不足时触发补足回路。"""
        transcript = _make_transcript(20)

        mock_llm = AsyncMock()
        # 返回短脚本，触发补足回路
        mock_llm.complete = AsyncMock(
            return_value=_make_llm_result(content=_MOCK_SHORT_SCRIPT)
        )

        with patch(
            "podlator.steps.douyin_script.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.douyin_script import generate_douyin_script

            result = await generate_douyin_script(
                transcript,
                blueprint_provider="deepseek",
                finalize_provider="claude",
                target_words=6000,
            )

        # blueprint(1) + finalize(1) + supplement(最多 2 轮) = 至少 3 次
        assert mock_llm.complete.call_count >= 3
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_supplement_loop_not_triggered_when_long_enough(self) -> None:
        """字数达标时不触发补足回路。"""
        transcript = _make_transcript(20)

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=_make_llm_result(content=_MOCK_LONG_SCRIPT)
        )

        with patch(
            "podlator.steps.douyin_script.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.douyin_script import generate_douyin_script

            result = await generate_douyin_script(
                transcript,
                blueprint_provider="deepseek",
                finalize_provider="claude",
                target_words=100,  # 远低于 _MOCK_LONG_SCRIPT 的长度
            )

        # blueprint + finalize = 2 次，不触发补足
        assert mock_llm.complete.call_count == 2
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_blueprint_stage_logs_provider(self) -> None:
        """Stage1 日志包含 blueprint provider 信息。"""
        transcript = _make_transcript(20)

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=_make_llm_result(content=_MOCK_LONG_SCRIPT)
        )

        with patch(
            "podlator.steps.douyin_script.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.douyin_script import generate_douyin_script

            await generate_douyin_script(
                transcript,
                blueprint_provider="deepseek",
                finalize_provider="claude",
            )

        # 验证至少有一次调用传了 douyin_blueprint 的 system prompt
        # （blueprint 阶段用 blueprint prompt，finalize 阶段用 finalize prompt）
        # 通过检查 system 参数区分
        all_systems = [
            c.kwargs.get("system", "")
            for c in mock_llm.complete.call_args_list
            if c.kwargs.get("system")
        ]
        blueprint_calls = [s for s in all_systems if "结构策划" in s]
        finalize_calls = [s for s in all_systems if "解说稿写手" in s]
        assert len(blueprint_calls) >= 1, "blueprint 阶段应使用 douyin_blueprint prompt"
        assert len(finalize_calls) >= 1, "finalize 阶段应使用 douyin_finalize prompt"


# ── 字数补足回路专项测试 ──


class TestSupplementLoop:
    """字数补足回路专项测试。"""

    @pytest.mark.asyncio
    async def test_supplement_max_2_rounds(self) -> None:
        """补足回路最多 2 轮，之后即使字数不够也返回。"""
        transcript = _make_transcript(20)

        mock_llm = AsyncMock()
        # 始终返回短脚本
        mock_llm.complete = AsyncMock(
            return_value=_make_llm_result(content=_MOCK_SHORT_SCRIPT)
        )

        with patch(
            "podlator.steps.douyin_script.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.douyin_script import generate_douyin_script

            result = await generate_douyin_script(
                transcript,
                blueprint_provider="deepseek",
                finalize_provider="claude",
                target_words=6000,
            )

        # blueprint(1) + finalize(1) + supplement(最多 2) = 最多 4
        assert mock_llm.complete.call_count <= 4, (
            f"补足回路不应超过 2 轮，实际调用了 {mock_llm.complete.call_count} 次"
        )
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_supplement_appends_content(self) -> None:
        """补足内容被追加到草稿后面。"""
        transcript = _make_transcript(20)

        supplement_base = "这是补充的解说内容，包含更多深度分析和行业背景知识。"
        supplement_content = "（" + supplement_base * 200 + "）"

        # 第一次返回短脚本触发补足，第二次返回补充内容
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock()
        mock_llm.complete.side_effect = [
            # blueprint
            _make_llm_result(content="蓝图：三个核心论点"),
            # finalize (短脚本，触发补足)
            _make_llm_result(content=_MOCK_SHORT_SCRIPT),
            # supplement round 1 (足够长，一轮达到目标)
            _make_llm_result(content=supplement_content),
        ]

        with patch(
            "podlator.steps.douyin_script.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.douyin_script import generate_douyin_script

            result = await generate_douyin_script(
                transcript,
                blueprint_provider="deepseek",
                finalize_provider="claude",
                target_words=5000,  # min=4500，补充后约 5272 字，满足
            )

        assert _MOCK_SHORT_SCRIPT.strip() in result
        assert "补充的解说内容" in result


# ── Provider 配置测试 ──


class TestProviderSelection:
    """Provider 选择测试。"""

    @pytest.mark.asyncio
    async def test_defaults_to_config_providers(self) -> None:
        """未指定 provider 时使用 config 默认值。"""
        transcript = _make_transcript(20)

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=_make_llm_result(content=_MOCK_LONG_SCRIPT)
        )

        with patch(
            "podlator.steps.douyin_script.get_llm_provider",
            return_value=mock_llm,
        ) as mock_get:
            from podlator.steps.douyin_script import generate_douyin_script

            await generate_douyin_script(transcript)

        # get_llm_provider 被调用了（blueprint_provider 默认用 summarize，
        # finalize_provider 默认用 polish）
        assert mock_get.call_count >= 2

    @pytest.mark.asyncio
    async def test_custom_blueprint_and_finalize_providers(self) -> None:
        """可以自定义 blueprint 和 finalize 的 provider。"""
        transcript = _make_transcript(20)

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=_make_llm_result(content=_MOCK_LONG_SCRIPT)
        )

        with patch(
            "podlator.steps.douyin_script.get_llm_provider",
            return_value=mock_llm,
        ) as mock_get:
            from podlator.steps.douyin_script import generate_douyin_script

            await generate_douyin_script(
                transcript,
                blueprint_provider="deepseek",
                finalize_provider="claude_cli",
            )

        # 验证 get_llm_provider 被调用了，参数包含自定义 provider
        provider_names = [args[0] for args, _ in mock_get.call_args_list]
        assert "deepseek" in provider_names
        assert "claude_cli" in provider_names
