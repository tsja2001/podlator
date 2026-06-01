"""Step: URL → 音频文件 + metadata JSON。

封装下载逻辑，CLI 和 LangGraph 共享。
"""

from __future__ import annotations

from pathlib import Path

from podlator.config import Settings
from podlator.providers.downloader import get_downloader
from podlator.providers.downloader.base import DownloadResult, MediaMetadata


async def download_audio(
    url: str,
    *,
    output_dir: Path | None = None,
    settings: Settings | None = None,
) -> tuple[DownloadResult, MediaMetadata]:
    """下载音频并获取元数据。

    Args:
        url: YouTube 或播客 URL。
        output_dir: 音频输出目录（默认从配置读取）。
        settings: 应用配置。

    Returns:
        (DownloadResult, MediaMetadata) 元组。
    """
    if settings is None:
        settings = Settings()

    downloader = get_downloader(settings)
    target_dir = output_dir or settings.audio_dir

    result = await downloader.download(url, output_dir=target_dir)
    metadata = await downloader.fetch_metadata(url)

    return result, metadata


async def download_to_file(
    url: str,
    audio_output: Path,
    *,
    metadata_output: Path | None = None,
    settings: Settings | None = None,
) -> tuple[Path, MediaMetadata | None]:
    """下载音频到指定路径，可选写 metadata JSON。

    Args:
        url: YouTube 或播客 URL。
        audio_output: 音频输出文件路径。
        metadata_output: metadata JSON 输出路径（可选）。
        settings: 应用配置。

    Returns:
        (audio_path, metadata) 元组。
    """
    import json
    import shutil

    result, metadata = await download_audio(url, settings=settings)

    audio_output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(result.file_path), audio_output)

    if metadata_output:
        meta_dict = {
            "title": metadata.title,
            "description": metadata.description,
            "duration_seconds": metadata.duration_seconds,
            "published_at": metadata.published_at,
            "source_type": metadata.source_type,
            "thumbnail_url": metadata.thumbnail_url,
        }
        metadata_output.parent.mkdir(parents=True, exist_ok=True)
        metadata_output.write_text(
            json.dumps(meta_dict, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return audio_output, metadata
