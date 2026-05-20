"""节点：说话人分离（如 STT 未自带）。M0 占位实现。"""

from __future__ import annotations

from typing import Any

from podlator.graph.nodes._base import node, node_logger
from podlator.graph.state import PodlatorState


@node("diarize")
async def run(state: PodlatorState) -> dict[str, Any]:
    log = node_logger(state, "diarize")
    log.info("not_implemented", reason="M0 placeholder")
    return {}
