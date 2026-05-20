"""YtDlp Downloader Smoke 测试 — 需要真实网络。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from podlator.providers.downloader.ytdlp import YtDlpDownloader

pytestmark = pytest.mark.skipif(
    not os.getenv("PODLATOR_RUN_SMOKE"),
    reason="Smoke tests disabled (set PODLATOR_RUN_SMOKE=1)",
)

# 19 秒的 YouTube 第一个视频
TEST_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"


@pytest.mark.asyncio
async def test_fetch_metadata_real() -> None:
    """真实 API 获取元数据。"""
    dl = YtDlpDownloader()
    meta = await dl.fetch_metadata(TEST_URL)
    assert meta.title
    assert meta.duration_seconds > 0


@pytest.mark.asyncio
async def test_download_audio_real(tmp_path: Path) -> None:
    """真实下载音频文件。"""
    dl = YtDlpDownloader()
    result = await dl.download(TEST_URL, output_dir=tmp_path)
    assert result.file_path.exists()
    assert result.size_bytes > 0
