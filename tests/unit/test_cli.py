"""CLI 命令测试。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from podlator.cli import app

runner = CliRunner()


def test_version() -> None:
    """版本命令正常输出。"""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "podlator" in result.stdout


def test_run_help() -> None:
    """run 命令显示帮助。"""
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "URL" in result.stdout


def test_status_no_args(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """无参数 status 显示最近任务或暂无任务。"""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "暂无任务" in result.stdout


def test_status_specific_task(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """指定 task_id 查询 status，不存在的任务返回错误。"""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    result = runner.invoke(app, ["status", "nonexistent-id"])
    assert result.exit_code == 1
    assert "任务不存在" in result.stderr or "任务不存在" in result.stdout


def test_list_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """空任务列表正常输出。"""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "暂无任务" in result.stdout


def test_list_with_status_filter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """按状态过滤任务列表。"""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    result = runner.invoke(app, ["list", "--status", "completed"])
    assert result.exit_code == 0


def test_run_command_mock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run 命令触发 pipeline 执行（mock graph）。"""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {
        "task_id": "test-001",
        "source_url": "https://example.com/video",
        "title": "Mock Episode",
        "output_path": str(tmp_path / "output.md"),
        "total_cost_usd": 0.005,
        "duration_seconds": 30.0,
    }

    with patch("podlator.graph.builder.build_graph", return_value=mock_graph):
        result = runner.invoke(app, ["run", "https://example.com/video"])

    assert result.exit_code == 0
    assert "✅ 处理完成" in result.stdout
    assert "输出" in result.stdout or "简报" in result.stdout
