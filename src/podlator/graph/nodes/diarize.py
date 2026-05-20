"""节点：说话人分离（如 STT 未自带）。M1 占位 — M4 实现 pyannote。"""

from __future__ import annotations

from typing import Any

from podlator.graph.nodes._base import node, node_logger
from podlator.graph.state import PodlatorState


@node("diarize")
async def run(state: PodlatorState) -> dict[str, Any]:
    log = node_logger(state, "diarize")

    if state.get("has_diarization", False):
        log.info("diarization_skipped", reason="STT already provided speaker labels")
        return {}

    log.warning(
        "diarization_not_implemented",
        reason="M4 will implement pyannote.audio integration",
    )
    return {}
