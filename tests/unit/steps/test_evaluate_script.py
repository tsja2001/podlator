"""evaluate_script 单元测试（M5.1 Phase 3）。Mock LLM provider。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from podlator.errors import ProviderError
from podlator.providers.llm.base import LLMResult
from podlator.steps.models import JudgeReport


@pytest.fixture
def valid_judge_json() -> dict:
    fixture_path = (
        Path(__file__).parent.parent.parent / "fixtures" / "judge_report_valid.json"
    )
    return json.loads(fixture_path.read_text())


def _make_stub(content: str) -> AsyncMock:
    """构造 mock LLM provider，返回指定 content。"""
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(
        return_value=LLMResult(
            content=content,
            model="test-judge",
            provider_name="deepseek",
            tokens_in=500,
            tokens_out=300,
            duration_ms=2000,
            cost_usd=0.002,
        )
    )
    return mock_llm


@pytest.mark.asyncio
async def test_evaluate_returns_report_on_valid_json(valid_judge_json: dict) -> None:
    """stub 返回合法 JSON → JudgeReport 正确，lint 硬伤已合并。"""
    from podlator.steps.evaluate_script import evaluate_script

    script = "今天我们来聊聊英伟达。内容完整流畅。"
    content = json.dumps(valid_judge_json, ensure_ascii=False)
    mock_llm = _make_stub(content)

    with patch(
        "podlator.steps.evaluate_script.get_llm_provider",
        return_value=mock_llm,
    ):
        report, lint_stats = await evaluate_script(script)

    assert isinstance(report, JudgeReport)
    assert report.rubric_version == "v3"
    assert report.total_score > 0
    assert len(report.dimensions) == 9
    assert lint_stats.char_count > 0


@pytest.mark.asyncio
async def test_evaluate_strips_json_codeblock_wrapper(
    valid_judge_json: dict,
) -> None:
    """stub 返回 ```json {...}``` 包裹 → 仍解析成功。"""
    from podlator.steps.evaluate_script import evaluate_script

    script = "正常稿件内容。"
    content = "```json\n" + json.dumps(valid_judge_json, ensure_ascii=False) + "\n```"
    mock_llm = _make_stub(content)

    with patch(
        "podlator.steps.evaluate_script.get_llm_provider",
        return_value=mock_llm,
    ):
        report, _lint_stats = await evaluate_script(script)

    assert isinstance(report, JudgeReport)
    assert report.verdict in ("pass", "needs_revision")


@pytest.mark.asyncio
async def test_evaluate_retries_once_on_invalid_json(
    valid_judge_json: dict,
) -> None:
    """第一次返回非 JSON、第二次合法 → 成功且 provider 被调 2 次。"""
    from podlator.steps.evaluate_script import evaluate_script

    script = "正常稿件。"
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(
        side_effect=[
            LLMResult(
                content="not valid json!!!",
                model="test",
                provider_name="deepseek",
                tokens_in=100,
                tokens_out=50,
                duration_ms=500,
                cost_usd=0.001,
            ),
            LLMResult(
                content=json.dumps(valid_judge_json, ensure_ascii=False),
                model="test",
                provider_name="deepseek",
                tokens_in=500,
                tokens_out=300,
                duration_ms=2000,
                cost_usd=0.002,
            ),
        ]
    )

    with patch(
        "podlator.steps.evaluate_script.get_llm_provider",
        return_value=mock_llm,
    ):
        report, _lint_stats = await evaluate_script(script)

    assert isinstance(report, JudgeReport)
    assert mock_llm.complete.call_count == 2


@pytest.mark.asyncio
async def test_evaluate_raises_after_two_invalid_json() -> None:
    """两次都返回非法 JSON → ProviderError(retryable=False)。"""
    from podlator.steps.evaluate_script import evaluate_script

    script = "正常稿件。"
    mock_llm = _make_stub("definitely not json at all")

    with patch(
        "podlator.steps.evaluate_script.get_llm_provider",
        return_value=mock_llm,
    ):
        with pytest.raises(ProviderError) as exc_info:
            await evaluate_script(script)

    assert exc_info.value.retryable is False
    assert mock_llm.complete.call_count == 2


@pytest.mark.asyncio
async def test_evaluate_recomputes_total_on_mismatch(
    valid_judge_json: dict,
) -> None:
    """stub 的 total_score 与维度和差 3 分 → 返回值应为代码重算结果。"""
    from podlator.steps.evaluate_script import evaluate_script

    script = "正常稿件。"
    # LLM 返回的 total_score 故意设错（差 5 分，> 0.5 阈值）
    bad_data = {**valid_judge_json, "total_score": valid_judge_json["total_score"] + 5}
    mock_llm = _make_stub(json.dumps(bad_data, ensure_ascii=False))

    with patch(
        "podlator.steps.evaluate_script.get_llm_provider",
        return_value=mock_llm,
    ):
        report, _lint_stats = await evaluate_script(script)

    # 代码重算应该修正回维度实际求和值
    assert report.total_score == valid_judge_json["total_score"]


@pytest.mark.asyncio
async def test_evaluate_skips_coverage_without_reference() -> None:
    """reference_points=None 时 judge 应收到「无参照论点清单」。"""
    from podlator.steps.evaluate_script import evaluate_script

    script = "正常稿件。"
    # Judge 返回覆盖度 score=-1（无参照），total 按 /80*100 折算
    judge_data = {
        "rubric_version": "v3",
        "total_score": 87.5,
        "dimensions": [
            {
                "dimension": "信息覆盖度",
                "score": -1.0,
                "max_score": 20,
                "evidence": [],
                "issues": [],
            },
            {
                "dimension": "信息忠实度",
                "score": 9.0,
                "max_score": 10,
                "evidence": [],
                "issues": [],
            },
            {
                "dimension": "外部知识质量",
                "score": 12.0,
                "max_score": 15,
                "evidence": [],
                "issues": [],
            },
            {
                "dimension": "钩子开场",
                "score": 8.0,
                "max_score": 10,
                "evidence": [],
                "issues": [],
            },
            {
                "dimension": "结构与递进",
                "score": 10.0,
                "max_score": 12,
                "evidence": [],
                "issues": [],
            },
            {
                "dimension": "人物与现场感",
                "score": 6.0,
                "max_score": 8,
                "evidence": [],
                "issues": [],
            },
            {
                "dimension": "口语自然度",
                "score": 8.0,
                "max_score": 10,
                "evidence": [],
                "issues": [],
            },
            {
                "dimension": "节奏与听感",
                "score": 7.0,
                "max_score": 8,
                "evidence": [],
                "issues": [],
            },
            {
                "dimension": "术语白话化与数字可感",
                "score": 6.0,
                "max_score": 7,
                "evidence": [],
                "issues": [],
            },
        ],
        "revision_directives": [],
        "verdict": "pass",
    }
    # 手工重算：其余维度总分 = 9+12+8+10+6+8+7+6 = 66，满分 80
    # total = 66 / 80 * 100 = 82.5
    mock_llm = _make_stub(json.dumps(judge_data, ensure_ascii=False))

    with patch(
        "podlator.steps.evaluate_script.get_llm_provider",
        return_value=mock_llm,
    ):
        report, lint_stats = await evaluate_script(
            script,
            reference_points=None,
        )

    # 代码重算 > LLM 给的 87.5
    assert report.total_score == 82.5, f"Expected 82.5, got {report.total_score}"


@pytest.mark.asyncio
async def test_evaluate_verdict_overridden_by_code(
    valid_judge_json: dict,
) -> None:
    """stub verdict="pass" 但有维度 < 60% → 最终 needs_revision。"""
    from podlator.steps.evaluate_script import evaluate_script

    script = "正常稿件。"
    # 故意让一个维度得分 < 60%（max=10，score=5）
    bad_data = {
        **valid_judge_json,
        "verdict": "pass",
    }
    # 修改信息忠实度的得分为 5（10 分的 50% < 60%）
    bad_data["dimensions"][1] = {
        "dimension": "信息忠实度",
        "score": 5.0,
        "max_score": 10,
        "evidence": [],
        "issues": ["多处数字错误"],
    }
    mock_llm = _make_stub(json.dumps(bad_data, ensure_ascii=False))

    with patch(
        "podlator.steps.evaluate_script.get_llm_provider",
        return_value=mock_llm,
    ):
        report, _lint_stats = await evaluate_script(script)

    assert report.verdict == "needs_revision"
