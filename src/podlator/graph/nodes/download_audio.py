"""节点：下载音频到本地。M0 占位实现。"""

from __future__ import annotations

from typing import Any

from podlator.graph.nodes._base import node, node_logger
from podlator.graph.state import PodlatorState


@node("download_audio")
async def run(state: PodlatorState) -> dict[str, Any]:
    log = node_logger(state, "download_audio")
    log.info("not_implemented", reason="M0 placeholder")
    return {}
