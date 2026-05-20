"""Downloader Provider 模块。"""

from __future__ import annotations

from podlator.config import Settings
from podlator.providers.downloader.base import DownloaderProvider


def get_downloader(settings: Settings) -> DownloaderProvider:
    """返回 Downloader Provider 实例。"""
    from podlator.providers.downloader.ytdlp import YtDlpDownloader

    return YtDlpDownloader()
