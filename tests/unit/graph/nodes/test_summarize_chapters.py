"""summarize_chapters 节点测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from podlator.graph.nodes.summarize_chapters import run
from podlator.graph.state import Chapter


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
        "title": "Test Episode",
        "transcript_text": "hello world test content",
        "chapters": chapters,
        "transcript_segments": segments,
    }


SUMMARY_MARKDOWN = """\
# Test Episode

> 中文精简摘要

## 开场

开场摘要内容。

## 正文

正文摘要内容。
"""


@pytest.mark.asyncio
async def test_summarize_chapters_success(state: dict) -> None:
    """正常渲染，通过 step 层获取结果并解析到 summary_zh。"""
    with patch(
        "podlator.graph.nodes.summarize_chapters.render_chinese",
        new_callable=AsyncMock,
        return_value=SUMMARY_MARKDOWN,
    ):
        result = await run(state)

    assert len(result["chapter_summaries"]) == 2
    assert result["chapters"][0]["summary_zh"] == "开场摘要内容。"
    assert result["chapters"][1]["summary_zh"] == "正文摘要内容。"


@pytest.mark.asyncio
async def test_summarize_chapters_partial_failure(state: dict) -> None:
    """step 抛异常时 @node 包装为 NodeError。"""
    with patch(
        "podlator.graph.nodes.summarize_chapters.render_chinese",
        new_callable=AsyncMock,
        side_effect=RuntimeError("LLM API error"),
    ):
        with pytest.raises(Exception):
            # @node decorator wraps all exceptions in NodeError
            result = await run(state)
            # If we reach here, check it was wrapped
            assert "error" in result


@pytest.mark.asyncio
async def test_summarize_chapters_no_chapters() -> None:
    """无章节时返回空列表。"""
    result = await run({"task_id": "test", "chapters": [], "transcript_segments": []})
    assert result["chapter_summaries"] == []
