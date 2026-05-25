"""全局测试 fixtures。"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """确保测试不受真实 .env 影响。"""
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))


@pytest.fixture
def fixtures_dir() -> Path:
    """测试 fixtures 目录路径。"""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_state() -> dict:
    """最小可用的 PodlatorState。"""
    return {
        "task_id": "test-task-001",
        "source_url": "https://www.youtube.com/watch?v=test",
        "status": "pending",
        "current_node": "",
        "node_durations_ms": {},
        "total_cost_usd": 0.0,
    }
