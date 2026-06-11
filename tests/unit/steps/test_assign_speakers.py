"""Unit tests for assign_speakers step (mock LLM)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from podlator.providers.llm.base import LLMResult
from podlator.steps.models import (
    TranscriptDocument,
    TranscriptProviderMeta,
    TranscriptSegmentModel,
    TranscriptSource,
)

_SPEAKER_JSON = json.dumps(
    [
        {"index": 0, "speaker": "HOST"},
        {"index": 1, "speaker": "GUEST"},
        {"index": 2, "speaker": "HOST"},
    ]
)


def _make_transcript(speakers: list[str | None] | None = None) -> TranscriptDocument:
    """创建测试用 TranscriptDocument（3 segments）。"""
    if speakers is None:
        speakers = [None, None, None]

    segments = [
        TranscriptSegmentModel(
            index=i,
            start=i * 10.0,
            end=(i + 1) * 10.0,
            text=f"Speaker says something {i}.",
            speaker=spk,
        )
        for i, spk in enumerate(speakers)
    ]
    return TranscriptDocument(
        source=TranscriptSource(title="Test"),
        provider=TranscriptProviderMeta(name="srt"),
        text=" ".join(s.text for s in segments),
        segments=segments,
    )


class TestAssignSpeakers:
    @pytest.mark.asyncio
    async def test_assigns_speakers_from_llm(self) -> None:
        """正常路径：LLM 返回说话人标签，正确写回 segments。"""
        transcript = _make_transcript()
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content=_SPEAKER_JSON,
                model="test",
                provider_name="deepseek",
                tokens_in=100,
                tokens_out=50,
                duration_ms=500,
                cost_usd=0.001,
            )
        )

        with patch(
            "podlator.steps.assign_speakers.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.assign_speakers import assign_speakers

            result = await assign_speakers(transcript, provider_name="deepseek")

        assert result.segments[0].speaker == "HOST"
        assert result.segments[1].speaker == "GUEST"
        assert result.segments[2].speaker == "HOST"

    @pytest.mark.asyncio
    async def test_does_not_modify_text_or_timestamps(self) -> None:
        """验证 assign_speakers 只修改 speaker 字段，不改正文和时间戳。"""
        transcript = _make_transcript()
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content=_SPEAKER_JSON,
                model="test",
                provider_name="deepseek",
                tokens_in=100,
                tokens_out=50,
                duration_ms=500,
                cost_usd=0.001,
            )
        )

        with patch(
            "podlator.steps.assign_speakers.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.assign_speakers import assign_speakers

            result = await assign_speakers(transcript)

        for i, seg in enumerate(result.segments):
            orig = transcript.segments[i]
            assert seg.text == orig.text, f"Segment {i} text modified"
            assert seg.start == orig.start, f"Segment {i} start modified"
            assert seg.end == orig.end, f"Segment {i} end modified"

    @pytest.mark.asyncio
    async def test_empty_segments_returns_unchanged(self) -> None:
        """空 segments 时直接返回原 transcript。"""
        transcript = TranscriptDocument(
            source=TranscriptSource(title="Empty"),
            provider=TranscriptProviderMeta(name="srt"),
        )

        from podlator.steps.assign_speakers import assign_speakers

        result = await assign_speakers(transcript)
        assert result.segments == []

    @pytest.mark.asyncio
    async def test_llm_returns_invalid_json(self) -> None:
        """LLM 返回非法 JSON 时保持原 transcript 不变。"""
        transcript = _make_transcript()
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content="not valid json!!!",
                model="test",
                provider_name="deepseek",
                tokens_in=100,
                tokens_out=50,
                duration_ms=500,
                cost_usd=0.001,
            )
        )

        with patch(
            "podlator.steps.assign_speakers.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.assign_speakers import assign_speakers

            result = await assign_speakers(transcript)

        for seg in result.segments:
            assert seg.speaker is None

    @pytest.mark.asyncio
    async def test_partial_indices_in_llm_response(self) -> None:
        """LLM 只返回部分 index 时，缺失的保持原样。"""
        transcript = _make_transcript()
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content='[{"index": 0, "speaker": "HOST"}]',
                model="test",
                provider_name="deepseek",
                tokens_in=100,
                tokens_out=50,
                duration_ms=500,
                cost_usd=0.001,
            )
        )

        with patch(
            "podlator.steps.assign_speakers.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.assign_speakers import assign_speakers

            result = await assign_speakers(transcript)

        assert result.segments[0].speaker == "HOST"
        assert result.segments[1].speaker is None
        assert result.segments[2].speaker is None

    @pytest.mark.asyncio
    async def test_llm_returns_code_fenced_json(self) -> None:
        """LLM 返回 ```json ... ``` 包裹的 JSON 时能正确解析。"""
        transcript = _make_transcript()
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content="```json\n" + _SPEAKER_JSON + "\n```",
                model="test",
                provider_name="deepseek",
                tokens_in=100,
                tokens_out=50,
                duration_ms=500,
                cost_usd=0.001,
            )
        )

        with patch(
            "podlator.steps.assign_speakers.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.assign_speakers import assign_speakers

            result = await assign_speakers(transcript)

        assert result.segments[0].speaker == "HOST"
        assert result.segments[1].speaker == "GUEST"

    @pytest.mark.asyncio
    async def test_short_transcript_no_sharding(self) -> None:
        """边界条件：短 transcript 不触发分片，只调用一次 LLM。"""
        transcript = _make_transcript()
        call_count = [0]

        async def mock_complete(prompt, system=None, temperature=0.2, max_tokens=4096):
            call_count[0] += 1
            return LLMResult(
                content=_SPEAKER_JSON,
                model="test",
                provider_name="deepseek",
                tokens_in=100,
                tokens_out=50,
                duration_ms=500,
                cost_usd=0.001,
            )

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(side_effect=mock_complete)

        with patch(
            "podlator.steps.assign_speakers.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.assign_speakers import assign_speakers

            await assign_speakers(transcript, provider_name="deepseek", shard_size=80)

        assert call_count[0] == 1, f"Expected 1 call, got {call_count[0]}"


# ── Sharding 测试辅助函数 ──


def _make_long_transcript(n: int) -> TranscriptDocument:
    """创建有 n 个 segment 的测试用长 TranscriptDocument。"""
    segments = [
        TranscriptSegmentModel(
            index=i,
            start=i * 5.0,
            end=(i + 1) * 5.0,
            text=f"Segment {i} text here.",
            speaker=None,
        )
        for i in range(n)
    ]
    return TranscriptDocument(
        source=TranscriptSource(title=f"Long Test ({n} segments)"),
        provider=TranscriptProviderMeta(name="srt"),
        text=" ".join(s.text for s in segments),
        segments=segments,
    )


def _make_shard_json(
    indices: list[int], speaker_a: str = "HOST", speaker_b: str = "GUEST"
) -> str:
    """生成 mock shard LLM 响应，交替分配 speaker。"""
    items = []
    for idx in indices:
        spk = speaker_a if idx % 2 == 0 else speaker_b
        items.append({"index": idx, "speaker": spk})
    return json.dumps(items)


class TestAssignSpeakersSharding:
    """分片模式（长 transcript 触发 sharding）的测试。"""

    @pytest.mark.asyncio
    async def test_shards_long_transcript(self) -> None:
        """正常路径：200 segment 触发分片，全部标注说话人。"""
        transcript = _make_long_transcript(200)

        call_count = [0]

        async def mock_complete(prompt, system=None, temperature=0.2, max_tokens=4096):
            call_count[0] += 1
            import re

            found = [int(m) for m in re.findall(r"index=(\d+)", prompt)]
            content = _make_shard_json(found)
            return LLMResult(
                content=content,
                model="test",
                provider_name="deepseek",
                tokens_in=len(prompt),
                tokens_out=len(content),
                duration_ms=1000,
                cost_usd=0.01,
            )

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(side_effect=mock_complete)

        with patch(
            "podlator.steps.assign_speakers.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.assign_speakers import assign_speakers

            result = await assign_speakers(
                transcript,
                provider_name="deepseek",
                shard_size=80,
                shard_overlap=10,
            )

        assert call_count[0] >= 3, f"Expected ≥3 shards, got {call_count[0]}"
        for seg in result.segments:
            assert seg.speaker is not None, f"Segment {seg.index} speaker is None"

    @pytest.mark.asyncio
    async def test_shard_boundary_speaker_continuity(self) -> None:
        """边界条件：分片边界处说话人标签保持连续。

        模拟不同分片使用不同标签名（HOST/GUEST vs SPEAKER_A/SPEAKER_B），
        验证合并后标签归一化到第一个分片的标签。
        """
        transcript = _make_long_transcript(160)

        call_count = [0]

        async def mock_complete(prompt, system=None, temperature=0.2, max_tokens=4096):
            import re

            found = [int(m) for m in re.findall(r"index=(\d+)", prompt)]
            call_count[0] += 1
            if call_count[0] == 1:
                content = _make_shard_json(found, "HOST", "GUEST")
            else:
                content = _make_shard_json(found, "SPEAKER_A", "SPEAKER_B")
            return LLMResult(
                content=content,
                model="test",
                provider_name="deepseek",
                tokens_in=len(prompt),
                tokens_out=len(content),
                duration_ms=1000,
                cost_usd=0.01,
            )

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(side_effect=mock_complete)

        with patch(
            "podlator.steps.assign_speakers.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.assign_speakers import assign_speakers

            result = await assign_speakers(
                transcript,
                provider_name="deepseek",
                shard_size=80,
                shard_overlap=10,
            )

        speakers = {seg.speaker for seg in result.segments}
        assert "SPEAKER_A" not in speakers, f"SPEAKER_A not normalized: {speakers}"
        assert "SPEAKER_B" not in speakers, f"SPEAKER_B not normalized: {speakers}"
        expected = {"HOST", "GUEST"}
        assert speakers == expected, f"Expected {expected}, got {speakers}"

    @pytest.mark.asyncio
    async def test_single_speaker_all_same_label(self) -> None:
        """边界条件：单说话人，所有 segment 标注为同一标签。"""
        transcript = _make_long_transcript(5)

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content=json.dumps(
                    [{"index": i, "speaker": "NARRATOR"} for i in range(5)]
                ),
                model="test",
                provider_name="deepseek",
                tokens_in=100,
                tokens_out=50,
                duration_ms=500,
                cost_usd=0.001,
            )
        )

        with patch(
            "podlator.steps.assign_speakers.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.assign_speakers import assign_speakers

            result = await assign_speakers(transcript)

        unique = {seg.speaker for seg in result.segments}
        assert len(unique) == 1, f"Expected 1 speaker, got {unique}"

    @pytest.mark.asyncio
    async def test_one_shard_llm_fails_others_succeed(self) -> None:
        """失败路径：某一分片 LLM 返回非法 JSON，其他分片不受影响。"""
        transcript = _make_long_transcript(160)

        call_count = [0]

        async def mock_complete(prompt, system=None, temperature=0.2, max_tokens=4096):
            import re

            found = [int(m) for m in re.findall(r"index=(\d+)", prompt)]
            call_count[0] += 1
            if call_count[0] == 1:
                return LLMResult(
                    content=_make_shard_json(found),
                    model="test",
                    provider_name="deepseek",
                    tokens_in=200,
                    tokens_out=100,
                    duration_ms=500,
                    cost_usd=0.002,
                )
            else:
                return LLMResult(
                    content="not valid json!!!",
                    model="test",
                    provider_name="deepseek",
                    tokens_in=100,
                    tokens_out=50,
                    duration_ms=500,
                    cost_usd=0.001,
                )

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(side_effect=mock_complete)

        with patch(
            "podlator.steps.assign_speakers.get_llm_provider",
            return_value=mock_llm,
        ):
            from podlator.steps.assign_speakers import assign_speakers

            result = await assign_speakers(
                transcript,
                provider_name="deepseek",
                shard_size=80,
                shard_overlap=10,
            )

        assert result is not None
        assert len(result.segments) == 160
        # 第一片的 speaker 应该保留
        assert result.segments[0].speaker is not None


class TestM50TruncationHardening:
    """M5.0 截断加固相关测试。"""

    def test_default_shard_size_is_50(self) -> None:
        """验证默认分片大小已从 80 降到 50。"""
        from podlator.steps.assign_speakers import DEFAULT_SHARD_SIZE

        assert DEFAULT_SHARD_SIZE == 50

    def test_parse_salvages_truncated_json(self) -> None:
        """截断 JSON 应能正则抢救完整对象。"""
        from podlator.steps.assign_speakers import _parse_llm_content

        result = _parse_llm_content(
            '[{"index":0,"speaker":"HOST"},{"index":1,"speaker":"GU'
        )
        assert result is not None
        assert result == {0: "HOST"}

    def test_parse_salvage_logs_warning(self) -> None:
        """截断抢救时应有 assign_speakers_salvaged_partial_json 警告日志。"""
        import structlog

        from podlator.steps.assign_speakers import _parse_llm_content

        cap = structlog.testing.capture_logs()
        with cap as captured:
            _parse_llm_content('[{"index":0,"speaker":"HOST"},{"index":1,"speaker":"GU')

        salvage_events = [
            e
            for e in captured
            if e.get("event") == "assign_speakers_salvaged_partial_json"
        ]
        assert len(salvage_events) == 1
        assert salvage_events[0]["recovered"] == 1

    def test_parse_unsalvageable_returns_none(self) -> None:
        """完全无法抢救时返回 None（行为同旧版，保护回归）。"""
        from podlator.steps.assign_speakers import _parse_llm_content

        result = _parse_llm_content("not valid json!!!")
        assert result is None

    @pytest.mark.asyncio
    async def test_process_shard_truncation_keeps_partial(self) -> None:
        """截断后仍能救回已完成的标注，缺失的保持 None。（3 条里救回 2 条）"""
        import structlog

        from podlator.config import Settings
        from podlator.steps.assign_speakers import _process_shard

        transcript = _make_long_transcript(3)
        # 构造 3 条 JSON：前 2 条完整对象 + 第 3 条已截断（缺闭标签）
        truncated_json = (
            '[{"index":0,"speaker":"HOST"},'
            '{"index":1,"speaker":"GUEST"},'
            '{"index":2,"speaker":"HO'
        )
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content=truncated_json,
                model="test",
                provider_name="deepseek",
                tokens_in=200,
                tokens_out=8192,
                duration_ms=1000,
                cost_usd=0.01,
                finish_reason="length",
            )
        )

        settings = Settings()
        cap = structlog.testing.capture_logs()
        with patch(
            "podlator.steps.assign_speakers.get_llm_provider",
            return_value=mock_llm,
        ):
            with cap as captured:
                speaker_map = await _process_shard(
                    transcript.segments,
                    provider_name="deepseek",
                    settings=settings,
                )

        # index 0 和 1 被救回（完整对象），index 2 丢失（已截断）
        assert speaker_map.get(0) == "HOST"
        assert speaker_map.get(1) == "GUEST"
        assert 2 not in speaker_map

        # 断言出现 assign_speakers_shard_truncated
        truncation_events = [
            e for e in captured if e.get("event") == "assign_speakers_shard_truncated"
        ]
        assert len(truncation_events) == 1
