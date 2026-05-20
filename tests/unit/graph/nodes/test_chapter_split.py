"""chapter_split 节点测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from podlator.errors import NodeError
from podlator.graph.nodes.chapter_split import run
from podlator.providers.llm.base import LLMResult


@pytest.fixture
def state() -> dict:
    return {
        "task_id": "test-task",
        "transcript_text": "Hello world. This is a test transcript. " * 20,
        "duration_seconds": 120.0,
        "transcript_segments": [
            {
                "text": "hello",
                "start": 0.0,
                "end": 1.0,
                "speaker": "SPEAKER_0",
                "confidence": 0.9,
            },
            {
                "text": "test",
                "start": 1.0,
                "end": 2.0,
                "speaker": "SPEAKER_0",
                "confidence": 0.9,
            },
        ],
    }


@pytest.fixture
def mock_llm_result() -> LLMResult:
    return LLMResult(
        content=(
            '[{"title": "开场", "start": 0.0, "end": 60.0},'
            ' {"title": "正文", "start": 60.0, "end": 120.0}]'
        ),
        model="deepseek-v4-flash",
        provider_name="deepseek",
        tokens_in=100,
        tokens_out=50,
        duration_ms=500.0,
        cost_usd=0.001,
    )


@pytest.mark.asyncio
async def test_chapter_split_success(state: dict, mock_llm_result: LLMResult) -> None:
    """正常切分章节。"""
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = mock_llm_result

    with patch(
        "podlator.graph.nodes.chapter_split.get_llm_provider",
        return_value=mock_llm,
    ):
        result = await run(state)

    chapters = result["chapters"]
    assert len(chapters) == 2
    assert chapters[0]["title"] == "开场"
    assert chapters[0]["summary_zh"] == ""


@pytest.mark.asyncio
async def test_chapter_split_invalid_json(state: dict) -> None:
    """LLM 返回无法解析的内容。"""
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = LLMResult(
        content="This is not JSON at all",
        model="deepseek-v4-flash",
        provider_name="deepseek",
        tokens_in=100,
        tokens_out=10,
        duration_ms=100.0,
        cost_usd=0.001,
    )

    with patch(
        "podlator.graph.nodes.chapter_split.get_llm_provider",
        return_value=mock_llm,
    ):
        with pytest.raises(NodeError, match=r"\[chapter_split\]"):
            await run(state)


@pytest.mark.asyncio
async def test_chapter_split_empty_transcript() -> None:
    """空转录稿返回空章节列表。"""
    result = await run(
        {
            "task_id": "test",
            "transcript_text": "",
            "duration_seconds": 0,
        }
    )
    assert result["chapters"] == []
