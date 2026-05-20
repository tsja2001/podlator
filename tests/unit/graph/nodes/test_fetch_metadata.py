"""fetch_metadata 节点测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from podlator.errors import NodeError, ProviderError
from podlator.graph.nodes.fetch_metadata import run
from podlator.providers.downloader.base import MediaMetadata


@pytest.fixture
def fake_metadata() -> MediaMetadata:
    return MediaMetadata(
        title="Test Episode",
        description="A test episode",
        duration_seconds=1800.0,
        published_at="2026-01-01T00:00:00Z",
        source_type="youtube",
        thumbnail_url="https://example.com/thumb.jpg",
    )


@pytest.fixture
def state() -> dict:
    return {
        "task_id": "test-task",
        "source_url": "https://www.youtube.com/watch?v=test",
    }


@pytest.mark.asyncio
async def test_fetch_metadata_success(
    state: dict, fake_metadata: MediaMetadata
) -> None:
    """正常获取元数据，返回正确的 state patch。"""
    mock_dl = AsyncMock()
    mock_dl.fetch_metadata.return_value = fake_metadata

    with patch(
        "podlator.graph.nodes.fetch_metadata.get_downloader",
        return_value=mock_dl,
    ):
        result = await run(state)

    assert result["title"] == "Test Episode"
    assert result["duration_seconds"] == 1800.0
    assert result["source_type"] == "youtube"
    assert result["thumbnail_url"] == "https://example.com/thumb.jpg"


@pytest.mark.asyncio
async def test_fetch_metadata_provider_error(state: dict) -> None:
    """Provider 失败时装饰器包装为 NodeError。"""
    mock_dl = AsyncMock()
    mock_dl.fetch_metadata.side_effect = ProviderError(
        "ytdlp", "Download error", retryable=True
    )

    with patch(
        "podlator.graph.nodes.fetch_metadata.get_downloader",
        return_value=mock_dl,
    ):
        with pytest.raises(NodeError, match=r"\[fetch_metadata\]"):
            await run(state)


@pytest.mark.asyncio
async def test_fetch_metadata_missing_url() -> None:
    """缺少 source_url 时返回空 dict。"""
    result = await run({"task_id": "no-url"})
    assert result == {} or "title" not in result
