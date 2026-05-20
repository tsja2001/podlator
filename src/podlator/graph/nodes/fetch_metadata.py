"""节点：获取媒体元数据（标题、时长、发布时间）。"""

from __future__ import annotations

from typing import Any

from podlator.config import Settings
from podlator.graph.nodes._base import node, node_logger
from podlator.graph.state import PodlatorState
from podlator.providers.downloader import get_downloader


@node("fetch_metadata")
async def run(state: PodlatorState) -> dict[str, Any]:
    log = node_logger(state, "fetch_metadata")

    source_url = state.get("source_url", "")
    if not source_url:
        log.error("missing_source_url")
        return {}

    settings = Settings()
    downloader = get_downloader(settings)

    metadata = await downloader.fetch_metadata(source_url)

    log.info(
        "metadata_fetched",
        title=metadata.title,
        duration_seconds=metadata.duration_seconds,
        source_type=metadata.source_type,
    )

    return {
        "title": metadata.title,
        "description": metadata.description,
        "duration_seconds": metadata.duration_seconds,
        "published_at": metadata.published_at,
        "source_type": metadata.source_type,
        "thumbnail_url": metadata.thumbnail_url,
    }
