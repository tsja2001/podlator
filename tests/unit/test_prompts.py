"""Prompt 加载工具测试。"""

from __future__ import annotations

import pytest

from podlator.prompts import load_prompt, load_rubric


class TestLoadRubric:
    def test_load_rubric_v3_returns_full_text(self) -> None:
        """载入 rubric v3 全文，应包含关键章节。"""
        text = load_rubric("v3")
        assert "信息覆盖度" in text
        assert "术语白话化与数字可感" in text
        assert "判定规则" in text

    def test_load_rubric_missing_version_raises_with_available_list(self) -> None:
        """载入不存在的版本应抛 FileNotFoundError 且消息含可用版本。"""
        with pytest.raises(FileNotFoundError) as exc_info:
            load_rubric("v99")
        msg = str(exc_info.value)
        assert "v99" in msg
        assert "rubric_v3" in msg


class TestLoadPrompt:
    def test_judge_score_has_placeholders(self) -> None:
        """judge_score 的 user 模板应包含全部四个槽位。"""
        _system, user = load_prompt("judge_score")
        assert "{rubric}" in user
        assert "{script}" in user
        assert "{reference_points}" in user
        assert "{lint_stats}" in user
