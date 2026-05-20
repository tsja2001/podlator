"""节点：下载音频到本地。"""

from __future__ import annotations

from typing import Any

from podlator.config import Settings
from podlator.graph.nodes._base import node, node_logger
from podlator.graph.state import PodlatorState
from podlator.providers.downloader import get_downloader
from podlator.storage.paths import get_audio_dir


@node("download_audio")
async def run(state: PodlatorState) -> dict[str, Any]:
    log = node_logger(state, "download_audio")

    source_url = state.get("source_url", "")
    task_id = state.get("task_id", "unknown")
    if not source_url:
        log.error("missing_source_url")
        return {}

    settings = Settings()
    downloader = get_downloader(settings)
    output_dir = get_audio_dir(settings.data_dir, task_id)

    result = await downloader.download(source_url, output_dir=output_dir)

    log.info(
        "audio_downloaded",
        path=str(result.file_path),
        size_bytes=result.size_bytes,
    )

    return {
        "audio_path": str(result.file_path),
        "audio_format": result.format,
        "audio_size_bytes": result.size_bytes,
    }
