"""全局测试 fixtures。"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """确保测试不受真实 .env 影响。"""
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)


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
