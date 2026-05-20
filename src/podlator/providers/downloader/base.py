"""音频下载 Provider 接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DownloadResult:
    """下载结果。"""

    file_path: Path
    format: str
    size_bytes: int
    duration_seconds: float


@dataclass
class MediaMetadata:
    """媒体元数据。"""

    title: str
    description: str
    duration_seconds: float
    published_at: str
    source_type: str
    thumbnail_url: str


class DownloaderProvider(ABC):
    """音频下载 Provider 接口。"""

    @abstractmethod
    async def download(
        self,
        url: str,
        *,
        output_dir: Path,
        audio_format: str = "mp3",
    ) -> DownloadResult:
        """下载音频文件到本地。"""
        ...

    @abstractmethod
    async def fetch_metadata(self, url: str) -> MediaMetadata:
        """获取媒体元数据（不下载文件）。"""
        ...
