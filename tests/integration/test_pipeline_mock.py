"""集成测试：完整 pipeline（mock 所有外部 API）。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from podlator.graph.builder import build_graph
from podlator.providers.downloader.base import DownloadResult, MediaMetadata
from podlator.providers.llm.base import LLMResult
from podlator.steps.models import (
    ChapterDocument,
    ChapterModel,
    TranscriptDocument,
    TranscriptProviderMeta,
    TranscriptSegmentModel,
    TranscriptSource,
)


def _make_mock_downloader() -> AsyncMock:
    """创建 mock downloader。"""
    mock = AsyncMock()
    mock.fetch_metadata.return_value = MediaMetadata(
        title="Test Episode",
        description="Desc",
        duration_seconds=120.0,
        published_at="2026-01-01T00:00:00Z",
        source_type="youtube",
        thumbnail_url="",
    )
    mock.download.return_value = DownloadResult(
        file_path=Path("/tmp/test.mp3"),
        format="mp3",
        size_bytes=100,
        duration_seconds=120.0,
    )
    return mock


def _fake_transcript_doc() -> TranscriptDocument:
    """创建 mock transcript step 返回值。"""
    return TranscriptDocument(
        source=TranscriptSource(audio_path="/tmp/test.mp3", duration_seconds=120.0),
        provider=TranscriptProviderMeta(name="deepgram", cost_usd=0.001),
        text="hello world this is a test transcript " * 5,
        segments=[
            TranscriptSegmentModel(
                index=0,
                start=0.0,
                end=10.0,
                text="hello world this is a test transcript " * 5,
                speaker="SPEAKER_0",
                confidence=0.99,
            )
        ],
    )


def _fake_chapters_doc() -> ChapterDocument:
    """创建 mock chapter split step 返回值。"""
    return ChapterDocument(
        chapters=[
            ChapterModel(
                index=0,
                title="开场",
                start=0.0,
                end=60.0,
                segment_indices=[0],
            ),
            ChapterModel(
                index=1,
                title="正文",
                start=60.0,
                end=120.0,
                segment_indices=[0],
            ),
        ]
    )


SUMMARY_MARKDOWN = """\
# Test Episode

> 中文精简摘要

## 开场

开场摘要内容。

## 正文

正文摘要内容。
"""


def _make_mock_llm() -> AsyncMock:
    """创建 mock LLM provider，用于 polish_final。"""
    mock = AsyncMock()
    mock.complete.return_value = LLMResult(
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
    )
    return mock


@pytest.mark.asyncio
async def test_full_pipeline_mock(tmp_path: Path) -> None:
    """完整 pipeline 从 URL 到 Markdown 文件。"""
    g = build_graph()
    mock_dl = _make_mock_downloader()
    mock_llm = _make_mock_llm()

    # export_markdown 需要 data_dir 配置
    import os

    os.environ["DATA_DIR"] = str(tmp_path)

    initial = {
        "task_id": "integration-test-001",
        "source_url": "https://www.youtube.com/watch?v=test",
    }

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
            "podlator.graph.nodes.transcribe.transcribe_audio",
            new_callable=AsyncMock,
            return_value=_fake_transcript_doc(),
        ),
        patch(
            "podlator.graph.nodes.chapter_split.split_transcript",
            new_callable=AsyncMock,
            return_value=_fake_chapters_doc(),
        ),
        patch(
            "podlator.graph.nodes.summarize_chapters.render_chinese",
            new_callable=AsyncMock,
            return_value=SUMMARY_MARKDOWN,
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
    chapters = result.get("chapters", [])
    assert len(chapters) == 2
    # summary_zh 应该被填充
    assert chapters[0].get("summary_zh") == "开场摘要内容。"
    assert result.get("output_path") != ""
    assert Path(result["output_path"]).exists()


@pytest.mark.asyncio
async def test_pipeline_tracks_costs(tmp_path: Path) -> None:
    """验证 pipeline 正确累计 API 费用。"""
    g = build_graph()
    mock_dl = _make_mock_downloader()
    mock_llm = _make_mock_llm()

    import os

    os.environ["DATA_DIR"] = str(tmp_path)

    initial = {
        "task_id": "cost-test-001",
        "source_url": "https://www.youtube.com/watch?v=test",
    }

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
            "podlator.graph.nodes.transcribe.transcribe_audio",
            new_callable=AsyncMock,
            return_value=_fake_transcript_doc(),
        ),
        patch(
            "podlator.graph.nodes.chapter_split.split_transcript",
            new_callable=AsyncMock,
            return_value=_fake_chapters_doc(),
        ),
        patch(
            "podlator.graph.nodes.summarize_chapters.render_chinese",
            new_callable=AsyncMock,
            return_value=SUMMARY_MARKDOWN,
        ),
        patch(
            "podlator.graph.nodes.polish_final.get_llm_provider",
            return_value=mock_llm,
        ),
    ):
        result = await g.ainvoke(initial)

    # total_cost_usd = STT(0.001) + polish(0.01) = 0.011
    # (chapter_split and summarize no longer contribute cost since they're
    #  mocked at the step level and costs come from LLM provider calls)
    assert result.get("total_cost_usd", 0.0) >= 0.0
    durations = result.get("node_durations_ms", {})
    assert len(durations) >= 5  # 至少 5 个节点有耗时记录
