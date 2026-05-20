"""summarize_chapters 节点测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from podlator.graph.nodes.summarize_chapters import run
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
            "summary_zh": "",
        },
        {
            "index": 1,
            "title": "正文",
            "start": 60.0,
            "end": 120.0,
            "segment_indices": [2, 3],
            "summary_zh": "",
        },
    ]
    segments = [
        {
            "text": "hello",
            "start": 0.0,
            "end": 1.0,
            "speaker": "SPEAKER_0",
            "confidence": 0.9,
        },
        {
            "text": "world",
            "start": 1.0,
            "end": 2.0,
            "speaker": "SPEAKER_0",
            "confidence": 0.9,
        },
        {
            "text": "test",
            "start": 60.0,
            "end": 61.0,
            "speaker": "SPEAKER_1",
            "confidence": 0.9,
        },
        {
            "text": "content",
            "start": 61.0,
            "end": 62.0,
            "speaker": "SPEAKER_1",
            "confidence": 0.9,
        },
    ]
    return {
        "task_id": "test-task",
        "chapters": chapters,
        "transcript_segments": segments,
    }


def _make_result(content: str) -> LLMResult:
    return LLMResult(
        content=content,
        model="deepseek-v4-flash",
        provider_name="deepseek",
        tokens_in=100,
        tokens_out=50,
        duration_ms=500.0,
        cost_usd=0.001,
    )


@pytest.mark.asyncio
async def test_summarize_chapters_success(state: dict) -> None:
    """正常并发摘要，所有 chapter.summary_zh 被填充。"""
    mock_llm = AsyncMock()
    mock_llm.complete.side_effect = [
        _make_result("开场摘要"),
        _make_result("正文摘要"),
    ]

    with patch(
        "podlator.graph.nodes.summarize_chapters.get_llm_provider",
        return_value=mock_llm,
    ):
        result = await run(state)

    assert len(result["chapter_summaries"]) == 2
    assert result["chapters"][0]["summary_zh"] == "开场摘要"
    assert result["chapters"][1]["summary_zh"] == "正文摘要"


@pytest.mark.asyncio
async def test_summarize_chapters_partial_failure(state: dict) -> None:
    """部分章节失败时继续处理其他。"""
    mock_llm = AsyncMock()
    mock_llm.complete.side_effect = [
        _make_result("开场摘要"),
        Exception("API error"),
    ]

    with patch(
        "podlator.graph.nodes.summarize_chapters.get_llm_provider",
        return_value=mock_llm,
    ):
        result = await run(state)

    # 第一个成功，第二个失败
    assert result["chapters"][0]["summary_zh"] == "开场摘要"
    assert result["chapters"][1]["summary_zh"] == ""


@pytest.mark.asyncio
async def test_summarize_chapters_no_chapters() -> None:
    """无章节时返回空列表。"""
    result = await run({"task_id": "test", "chapters": [], "transcript_segments": []})
    assert result["chapter_summaries"] == []
