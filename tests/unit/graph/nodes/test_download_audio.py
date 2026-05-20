"""download_audio 节点测试。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from podlator.errors import NodeError, ProviderError
from podlator.graph.nodes.download_audio import run
from podlator.providers.downloader.base import DownloadResult


@pytest.fixture
def state() -> dict:
    return {
        "task_id": "test-task",
        "source_url": "https://www.youtube.com/watch?v=test",
    }


@pytest.fixture
def fake_result(tmp_path: Path) -> DownloadResult:
    p = tmp_path / "audio.mp3"
    p.write_bytes(b"data")
    return DownloadResult(
        file_path=p,
        format="mp3",
        size_bytes=4,
        duration_seconds=10.0,
    )


@pytest.mark.asyncio
async def test_download_audio_success(state: dict, fake_result: DownloadResult) -> None:
    """正常下载，返回正确的 state patch。"""
    mock_dl = AsyncMock()
    mock_dl.download.return_value = fake_result

    with patch(
        "podlator.graph.nodes.download_audio.get_downloader",
        return_value=mock_dl,
    ):
        result = await run(state)

    assert "audio_path" in result
    assert result["audio_format"] == "mp3"


@pytest.mark.asyncio
async def test_download_audio_provider_error(state: dict) -> None:
    """Provider 失败时抛出 NodeError。"""
    mock_dl = AsyncMock()
    mock_dl.download.side_effect = ProviderError(
        "ytdlp", "Network error", retryable=True
    )

    with patch(
        "podlator.graph.nodes.download_audio.get_downloader",
        return_value=mock_dl,
    ):
        with pytest.raises(NodeError, match=r"\[download_audio\]"):
            await run(state)


@pytest.mark.asyncio
async def test_download_audio_missing_url() -> None:
    """缺少 source_url 返回空。"""
    result = await run({"task_id": "no-url"})
    assert result == {} or "audio_path" not in result
