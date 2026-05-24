"""后台 pipeline 执行入口。"""

from __future__ import annotations

from typing import Any

from podlator.graph.builder import build_graph
from podlator.logging import get_logger
from podlator.storage.db import TaskStore

logger = get_logger(__name__)


async def run_pipeline_background(
    task_id: str,
    source_url: str,
    store: TaskStore,
) -> None:
    """执行单个任务并把最终状态写回数据库。"""
    await store.update(task_id, status="running", current_node="fetch_metadata")
    logger.info("task_started", task_id=task_id, source_url=source_url)

    initial_state: dict[str, Any] = {
        "task_id": task_id,
        "source_url": source_url,
        "status": "running",
        "current_node": "",
        "node_durations_ms": {},
        "total_cost_usd": 0.0,
    }

    try:
        graph = build_graph()
        final_state = await graph.ainvoke(initial_state)  # type: ignore[call-overload]
        await store.update(
            task_id,
            status="completed",
            current_node=final_state.get("current_node"),
            title=final_state.get("title"),
            brief_path=final_state.get("output_path"),
            audio_path=final_state.get("audio_path"),
            cost_usd=final_state.get("total_cost_usd", 0.0),
            duration_seconds=final_state.get("duration_seconds"),
            error_message=None,
        )
        logger.info(
            "task_completed",
            task_id=task_id,
            output_path=final_state.get("output_path"),
            cost_usd=final_state.get("total_cost_usd", 0.0),
        )
    except Exception as exc:
        logger.error(
            "task_failed",
            task_id=task_id,
            error_type=type(exc).__name__,
            error_msg=str(exc),
            exc_info=True,
        )
        await store.update(task_id, status="failed", error_message=str(exc))
