"""YtDlp 下载 Provider 实现。"""

from __future__ import annotations

import asyncio
import glob
from datetime import datetime
from pathlib import Path

import yt_dlp  # type: ignore[import-untyped]

from podlator.errors import ProviderError
from podlator.logging import get_logger
from podlator.providers.downloader.base import (
    DownloaderProvider,
    DownloadResult,
    MediaMetadata,
)

logger = get_logger(__name__)


class YtDlpDownloader(DownloaderProvider):
    """基于 yt-dlp 的音频下载器。"""

    async def fetch_metadata(self, url: str) -> MediaMetadata:
        """获取媒体元数据（不下载文件）。"""
        log = logger.bind()
        ydl_opts = {"quiet": True, "no_warnings": True}

        try:
            info = await asyncio.to_thread(
                lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(url, download=False)
            )
        except yt_dlp.utils.DownloadError as e:
            log.error(
                "metadata_fetch_failed",
                url=url,
                error_msg=str(e),
            )
            raise ProviderError("ytdlp", str(e), retryable=False) from e

        title = info.get("title", "") or ""
        description = info.get("description", "") or ""
        duration = info.get("duration") or 0.0
        published_at = _parse_date(info.get("upload_date", ""))
        thumbnail = info.get("thumbnail", "") or ""
        source_type = _detect_source_type(url)

        log.info(
            "metadata_fetched",
            title=title,
            duration_seconds=duration,
            source_type=source_type,
        )
        return MediaMetadata(
            title=title,
            description=description,
            duration_seconds=float(duration),
            published_at=published_at,
            source_type=source_type,
            thumbnail_url=thumbnail,
        )

    async def download(
        self,
        url: str,
        *,
        output_dir: Path,
        audio_format: str = "mp3",
    ) -> DownloadResult:
        """下载音频文件到本地。"""
        log = logger.bind()
        output_dir.mkdir(parents=True, exist_ok=True)

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(output_dir / "audio.%(ext)s"),
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": audio_format,
                }
            ],
            "quiet": True,
            "no_warnings": True,
        }

        try:
            info = await asyncio.to_thread(
                lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(url, download=True)
            )
        except yt_dlp.utils.DownloadError as e:
            log.error(
                "audio_download_failed",
                url=url,
                error_msg=str(e),
            )
            raise ProviderError("ytdlp", str(e), retryable=True) from e

        # 查找下载文件（yt-dlp 可能改扩展名，如 m4a→mp3）
        files = glob.glob(str(output_dir / f"audio*.{audio_format}"))
        if not files:
            # 尝试任意扩展名
            files = glob.glob(str(output_dir / "audio.*"))
        outtmpl = str(ydl_opts["outtmpl"])
        actual_path = Path(files[0]) if files else Path(outtmpl)

        size_bytes = actual_path.stat().st_size if actual_path.exists() else 0
        duration = float(info.get("duration") or 0)

        log.info(
            "audio_downloaded",
            path=str(actual_path),
            size_bytes=size_bytes,
            duration_seconds=duration,
        )
        return DownloadResult(
            file_path=actual_path,
            format=audio_format,
            size_bytes=size_bytes,
            duration_seconds=duration,
        )


def _parse_date(upload_date: str) -> str:
    """yt-dlp 日期 YYYYMMDD → ISO 8601。"""
    if not upload_date or len(upload_date) != 8:
        return ""
    try:
        dt = datetime.strptime(upload_date, "%Y%m%d")
        return dt.isoformat() + "T00:00:00Z"
    except ValueError:
        return ""


def _detect_source_type(url: str) -> str:
    """根据 URL 判断来源类型。"""
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    if "podcast" in url or "itunes" in url or "rss" in url:
        return "podcast_rss"
    # 默认尝试判断为 youtube（yt-dlp 支持最广）
    return "youtube"
