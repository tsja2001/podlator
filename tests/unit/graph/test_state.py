"""PodlatorState 测试。"""

from __future__ import annotations

from podlator.graph.state import Chapter, PodlatorState, TranscriptSegment


def test_transcript_segment_creation() -> None:
    """TranscriptSegment 可用 TypedDict 方式创建。"""
    seg: TranscriptSegment = {
        "text": "hello",
        "start": 0.0,
        "end": 1.0,
        "speaker": None,
        "confidence": 0.99,
    }
    assert seg["text"] == "hello"


def test_chapter_creation() -> None:
    """Chapter 可用 TypedDict 方式创建。"""
    ch: Chapter = {
        "index": 0,
        "title": "开场",
        "start": 0.0,
        "end": 60.0,
        "segment_indices": [0, 1, 2],
        "summary_zh": "这是开场部分",
    }
    assert ch["title"] == "开场"
    assert ch["index"] == 0


def test_podlator_state_minimal() -> None:
    """PodlatorState 最小字段（total=False 允许部分字段）。"""
    state: PodlatorState = {
        "task_id": "abc",
        "source_url": "https://example.com",
    }
    assert state["task_id"] == "abc"
    assert state.get("title") is None
