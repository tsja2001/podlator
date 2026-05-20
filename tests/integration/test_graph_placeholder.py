"""Graph 集成测试。M1.2 模拟完整 pipeline，mock 所有 Provider。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from podlator.graph.builder import build_graph
from podlator.providers.downloader.base import DownloadResult, MediaMetadata
from podlator.providers.llm.base import LLMResult
from podlator.providers.stt.base import STTResult


@pytest.mark.asyncio
async def test_graph_can_invoke_with_initial_state() -> None:
    """Graph 能用 mock Provider 从头走到尾。"""
    g = build_graph()
    initial = {
        "task_id": "integration-test-001",
        "source_url": "https://www.youtube.com/watch?v=test",
    }

    # Mock downloader
    mock_dl = AsyncMock()
    mock_dl.fetch_metadata.return_value = MediaMetadata(
        title="Test Episode",
        description="Desc",
        duration_seconds=120.0,
        published_at="2026-01-01T00:00:00Z",
        source_type="youtube",
        thumbnail_url="",
    )
    mock_dl.download.return_value = DownloadResult(
        file_path=Path("/tmp/test.mp3"),
        format="mp3",
        size_bytes=100,
        duration_seconds=120.0,
    )

    # Mock STT provider
    mock_stt = AsyncMock()
    mock_stt.transcribe.return_value = STTResult(
        segments=[
            {
                "text": "hello world this is a test transcript " * 5,
                "start": 0.0,
                "end": 10.0,
                "speaker": "SPEAKER_0",
                "confidence": 0.99,
            }
        ],
        full_text="hello world this is a test transcript " * 5,
        has_diarization=True,
        provider_name="deepgram",
        duration_ms=100.0,
        cost_usd=0.001,
    )

    # Mock LLM provider (used by chapter_split + summarize_chapters + polish_final)
    mock_llm = AsyncMock()
    mock_llm.complete.side_effect = [
        # chapter_split: returns JSON chapters
        LLMResult(
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
        ),
        # summarize_chapters: chapter 1
        LLMResult(
            content="开场摘要内容。",
            model="deepseek-v4-flash",
            provider_name="deepseek",
            tokens_in=100,
            tokens_out=30,
            duration_ms=300.0,
            cost_usd=0.001,
        ),
        # summarize_chapters: chapter 2
        LLMResult(
            content="正文摘要内容。",
            model="deepseek-v4-flash",
            provider_name="deepseek",
            tokens_in=100,
            tokens_out=40,
            duration_ms=400.0,
            cost_usd=0.001,
        ),
        # polish_final: returns polished markdown (Claude)
        LLMResult(
            content=(
                "# Test Episode\n\n> 引言\n\n"
                "## 开场\n\n开场摘要内容。\n\n"
                "## 正文\n\n正文摘要内容。\n\n"
                "## 要点总结\n\n总结\n\n---\n\n"
                "*原始时长: 2 分钟 | 处理时间: 2026-05-20*"
            ),
            model="claude-opus-4.7",
            provider_name="claude",
            tokens_in=200,
            tokens_out=150,
            duration_ms=2000.0,
            cost_usd=0.01,
        ),
    ]

    with (
        patch(
            "podlator.graph.nodes.fetch_metadata.get_downloader",
            return_value=mock_dl,
        ),
        patch(
            "podlator.graph.nodes.download_audio.get_downloader",
            return_value=mock_dl,
        ),
        patch(
            "podlator.graph.nodes.transcribe.get_stt_provider",
            return_value=mock_stt,
        ),
        patch(
            "podlator.graph.nodes.chapter_split.get_llm_provider",
            return_value=mock_llm,
        ),
        patch(
            "podlator.graph.nodes.summarize_chapters.get_llm_provider",
            return_value=mock_llm,
        ),
        patch(
            "podlator.graph.nodes.polish_final.get_llm_provider",
            return_value=mock_llm,
        ),
    ):
        result = await g.ainvoke(initial)

    assert result is not None
    assert result.get("task_id") == "integration-test-001"
    assert result.get("title") == "Test Episode"
    assert result.get("transcript_text")
    assert result.get("brief_markdown")
    assert "Test Episode" in result["brief_markdown"]
    assert len(result.get("chapters", [])) == 2
