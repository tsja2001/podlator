"""节点：导出 Markdown 文件。"""

from __future__ import annotations

import re
from typing import Any

from podlator.config import Settings
from podlator.graph.nodes._base import node, node_logger
from podlator.graph.state import PodlatorState
from podlator.storage.paths import get_brief_dir


@node("export_markdown")
async def run(state: PodlatorState) -> dict[str, Any]:
    log = node_logger(state, "export_markdown")

    brief = state.get("brief_markdown", "")
    task_id = state.get("task_id", "unknown")
    title = state.get("title", "untitled")

    if not brief:
        log.warning("empty_brief", reason="No markdown content to export")
        return {"output_path": ""}

    settings = Settings()
    output_dir = get_brief_dir(settings.data_dir, task_id)
    safe_name = _slugify(title) or "brief"
    file_path = output_dir / f"{safe_name}.md"

    file_path.write_text(brief, encoding="utf-8")

    log.info(
        "markdown_exported", path=str(file_path), size_bytes=file_path.stat().st_size
    )
    return {"output_path": str(file_path)}


def _slugify(text: str) -> str:
    """将标题转为安全的文件名。"""
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[-\s]+", "-", text).strip("-")[:80]
