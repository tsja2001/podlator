"""polish_final 节点测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from podlator.graph.nodes.polish_final import run
from podlator.graph.state import Chapter
from podlator.providers.llm.base import LLMResult


@pytest.fixture
def state() -> dict:
    chapters: list[Chapter] = [
        {
            "index": 0,
            "title": "开场",
            "start": 0.0,
            "end": 60.0,
            "segment_indices": [0, 1],
            "summary_zh": "开场摘要内容。",
        },
        {
            "index": 1,
            "title": "正文",
            "start": 60.0,
            "end": 120.0,
            "segment_indices": [2, 3],
            "summary_zh": "正文摘要内容。",
        },
    ]
    return {
        "task_id": "test-task",
        "title": "Test Episode",
        "duration_seconds": 120.0,
        "chapters": chapters,
    }


@pytest.mark.asyncio
async def test_polish_final_success(state: dict) -> None:
    """正常润色，返回 brief_markdown。"""
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = LLMResult(
        content=(
            "# Test Episode\n\n> 引言\n\n## 开场\n\n开场摘要内容。\n\n"
            "## 正文\n\n正文摘要内容。\n\n## 要点总结\n\n总结"
        ),
        model="claude-opus-4.7",
        provider_name="claude",
        tokens_in=200,
        tokens_out=300,
        duration_ms=1000.0,
        cost_usd=0.02,
    )

    with patch(
        "podlator.graph.nodes.polish_final.get_llm_provider",
        return_value=mock_llm,
    ):
        result = await run(state)

    assert result["brief_markdown"]
    assert "Test Episode" in result["brief_markdown"]


@pytest.mark.asyncio
async def test_polish_final_no_chapters() -> None:
    """无章节时返回空 brief。"""
    result = await run(
        {
            "task_id": "test",
            "title": "Test",
            "chapters": [],
        }
    )
    assert result["brief_markdown"] == ""
