"""节点：章节翻译+精简（并发）。M0 占位实现。"""

from __future__ import annotations

from typing import Any

from podlator.graph.nodes._base import node, node_logger
from podlator.graph.state import PodlatorState


@node("summarize_chapters")
async def run(state: PodlatorState) -> dict[str, Any]:
    log = node_logger(state, "summarize_chapters")
    log.info("not_implemented", reason="M0 placeholder")
    return {}
