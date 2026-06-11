"""Eval 数据模型测试（M5.1）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from podlator.steps.models import DimensionScore, JudgeReport


@pytest.fixture
def valid_report_json() -> dict:
    fixture_path = (
        Path(__file__).parent.parent.parent / "fixtures" / "judge_report_valid.json"
    )
    return json.loads(fixture_path.read_text())


def test_judge_report_parses_valid_payload(valid_report_json: dict) -> None:
    """合法 dict → JudgeReport，verdict 字面量校验。"""
    report = JudgeReport(**valid_report_json)
    assert report.rubric_version == "v3"
    assert report.total_score == 84.0
    assert len(report.dimensions) == 9
    assert report.verdict == "pass"


def test_judge_report_rejects_unknown_verdict(valid_report_json: dict) -> None:
    """verdict="maybe" 应抛 ValidationError。"""
    data = {**valid_report_json, "verdict": "maybe"}
    with pytest.raises(ValidationError):
        JudgeReport(**data)


def test_dimension_score_allows_minus_one_for_skipped() -> None:
    """score=-1 合法（表示信息覆盖度无参照，跳过计分）。"""
    ds = DimensionScore(
        dimension="信息覆盖度",
        score=-1.0,
        max_score=20.0,
    )
    assert ds.score == -1.0
