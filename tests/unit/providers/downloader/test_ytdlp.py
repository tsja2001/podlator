"""YtDlpDownloader 单元测试。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from podlator.errors import ProviderError
from podlator.providers.downloader.ytdlp import YtDlpDownloader


@pytest.fixture
def ytdlp() -> YtDlpDownloader:
    return YtDlpDownloader()


_MOCK_INFO = {
    "title": "Test Episode",
    "description": "A test podcast episode",
    "duration": 1800,
    "upload_date": "20260101",
    "thumbnail": "https://example.com/thumb.jpg",
}


@pytest.mark.asyncio
async def test_fetch_metadata_youtube_url(ytdlp: YtDlpDownloader) -> None:
    """正常获取 YouTube 视频元数据。"""
    with patch("podlator.providers.downloader.ytdlp.asyncio.to_thread") as mock_to:
        mock_to.return_value = _MOCK_INFO
        result = await ytdlp.fetch_metadata("https://www.youtube.com/watch?v=test")

    assert result.title == "Test Episode"
    assert result.duration_seconds == 1800
    assert result.source_type == "youtube"
    assert result.thumbnail_url == "https://example.com/thumb.jpg"
    assert "2026-01-01" in result.published_at


@pytest.mark.asyncio
async def test_fetch_metadata_invalid_url(ytdlp: YtDlpDownloader) -> None:
    """无效 URL 抛出 ProviderError(retryable=False)。"""
    import yt_dlp

    with patch("podlator.providers.downloader.ytdlp.asyncio.to_thread") as mock_to:
        mock_to.side_effect = yt_dlp.utils.DownloadError("Video unavailable")
        with pytest.raises(ProviderError, match=r"\[ytdlp\]"):
            await ytdlp.fetch_metadata("https://invalid.url")


@pytest.mark.asyncio
async def test_download_audio_success(ytdlp: YtDlpDownloader, tmp_path: Path) -> None:
    """正常下载音频文件。"""
    output_dir = tmp_path / "audio"
    output_dir.mkdir()
    fake_file = output_dir / "audio.mp3"
    fake_file.write_bytes(b"\x00" * 1024)

    with patch("podlator.providers.downloader.ytdlp.asyncio.to_thread") as mock_to:
        mock_to.return_value = _MOCK_INFO
        result = await ytdlp.download(
            "https://www.youtube.com/watch?v=test",
            output_dir=output_dir,
        )

    assert result.format == "mp3"
    assert result.file_path.exists()
    assert result.size_bytes > 0


@pytest.mark.asyncio
async def test_download_audio_network_error(
    ytdlp: YtDlpDownloader, tmp_path: Path
) -> None:
    """网络错误抛出 ProviderError(retryable=True)。"""
    import yt_dlp

    with patch("podlator.providers.downloader.ytdlp.asyncio.to_thread") as mock_to:
        mock_to.side_effect = yt_dlp.utils.DownloadError("Network error")
        with pytest.raises(ProviderError) as exc_info:
            await ytdlp.download(
                "https://www.youtube.com/watch?v=test",
                output_dir=tmp_path,
            )

    assert exc_info.value.retryable is True
