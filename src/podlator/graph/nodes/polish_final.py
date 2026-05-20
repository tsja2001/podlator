"""节点：全局润色 + 引言/结论。M0 占位实现。"""

from __future__ import annotations

from typing import Any

from podlator.graph.nodes._base import node, node_logger
from podlator.graph.state import PodlatorState


@node("polish_final")
async def run(state: PodlatorState) -> dict[str, Any]:
    log = node_logger(state, "polish_final")
    log.info("not_implemented", reason="M0 placeholder")
    return {}
