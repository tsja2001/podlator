"""节点：获取媒体元数据（标题、时长、发布时间）。M0 占位实现。"""

from __future__ import annotations

from typing import Any

from podlator.graph.nodes._base import node, node_logger
from podlator.graph.state import PodlatorState


@node("fetch_metadata")
async def run(state: PodlatorState) -> dict[str, Any]:
    log = node_logger(state, "fetch_metadata")
    log.info("not_implemented", reason="M0 placeholder")
    return {}
