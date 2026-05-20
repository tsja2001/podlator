"""节点：按主题切分章节。M0 占位实现。"""

from __future__ import annotations

from typing import Any

from podlator.graph.nodes._base import node, node_logger
from podlator.graph.state import PodlatorState


@node("chapter_split")
async def run(state: PodlatorState) -> dict[str, Any]:
    log = node_logger(state, "chapter_split")
    log.info("not_implemented", reason="M0 placeholder")
    return {}
