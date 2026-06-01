"""chapter_split 节点测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from podlator.errors import NodeError
from podlator.graph.nodes.chapter_split import run
from podlator.steps.models import ChapterDocument, ChapterModel


@pytest.fixture
def state() -> dict:
    return {
        "task_id": "test-task",
        "transcript_text": "Hello world. This is a test transcript. " * 20,
        "duration_seconds": 120.0,
        "stt_provider": "deepgram",
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


def _fake_chapters_doc() -> ChapterDocument:
    return ChapterDocument(
        chapters=[
            ChapterModel(
                index=0, title="开场", start=0.0, end=60.0, segment_indices=[0]
            ),
            ChapterModel(
                index=1, title="正文", start=60.0, end=120.0, segment_indices=[1]
            ),
        ]
    )


@pytest.mark.asyncio
async def test_chapter_split_success(state: dict) -> None:
    """正常切分章节，通过 step 层获取结果并映射到 state。"""
    with patch(
        "podlator.graph.nodes.chapter_split.split_transcript",
        new_callable=AsyncMock,
        return_value=_fake_chapters_doc(),
    ):
        result = await run(state)

    chapters = result["chapters"]
    assert len(chapters) == 2
    assert chapters[0]["title"] == "开场"
    assert chapters[0]["summary_zh"] == ""


@pytest.mark.asyncio
async def test_chapter_split_error_wraps_to_node_error(state: dict) -> None:
    """step 抛异常时 @node 包装为 NodeError。"""
    with patch(
        "podlator.graph.nodes.chapter_split.split_transcript",
        new_callable=AsyncMock,
        side_effect=ValueError("LLM 章节切分返回非法 JSON"),
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
