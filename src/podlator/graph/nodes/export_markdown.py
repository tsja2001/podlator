"""节点：导出 Markdown 文件。M0 占位实现。"""

from __future__ import annotations

from typing import Any

from podlator.graph.nodes._base import node, node_logger
from podlator.graph.state import PodlatorState


@node("export_markdown")
async def run(state: PodlatorState) -> dict[str, Any]:
    log = node_logger(state, "export_markdown")
    log.info("not_implemented", reason="M0 placeholder")
    return {}
