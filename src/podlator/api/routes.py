"""REST API 路由。"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from podlator.api.schemas import (
    HealthResponse,
    TaskBriefResponse,
    TaskCreate,
    TaskResponse,
)
from podlator.logging import get_logger
from podlator.storage.db import TaskStore

logger = get_logger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """健康检查。"""
    return HealthResponse(status="ok")


@router.post("/tasks", status_code=201, response_model=TaskResponse)
async def create_task(
    body: TaskCreate,
    request: Request,
    background_tasks: BackgroundTasks,
) -> TaskResponse:
    """创建新任务并触发后台 pipeline 执行。"""
    store: TaskStore = request.app.state.store
    task_id = str(uuid.uuid4())
    record = await store.create(task_id, str(body.url))

    background_tasks.add_task(run_pipeline_background, task_id, str(body.url), store)

    return _to_response(record)


@router.get("/tasks", response_model=list[TaskResponse])
async def list_tasks(
    request: Request,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[TaskResponse]:
    """查询任务列表。"""
    store: TaskStore = request.app.state.store
    records = await store.list_tasks(status=status, limit=limit, offset=offset)
    return [_to_response(r) for r in records]


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, request: Request) -> TaskResponse:
    """查询单个任务。"""
    store: TaskStore = request.app.state.store
    record = await store.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return _to_response(record)


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: str, request: Request) -> None:
    """删除任务。"""
    store: TaskStore = request.app.state.store
    deleted = await store.delete(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")


@router.post("/tasks/{task_id}/retry", response_model=TaskResponse)
async def retry_task(
    task_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
) -> TaskResponse:
    """重试失败任务。"""
    store: TaskStore = request.app.state.store
    task = await store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] != "failed":
        raise HTTPException(
            status_code=400,
            detail=f"只能重试失败任务，当前状态: {task['status']}",
        )

    await store.update(task_id, status="pending", error_message=None, current_node=None)

    background_tasks.add_task(
        run_pipeline_background, task_id, task["source_url"], store
    )

    record = await store.get(task_id)
    return (
        _to_response(record)
        if record
        else TaskResponse(
            task_id=task_id,
            source_url=task["source_url"],
            title=task.get("title"),
            status="pending",
            current_node=None,
            error_message=None,
            cost_usd=0.0,
            created_at=task["created_at"],
            updated_at=task["updated_at"],
        )
    )


@router.get("/tasks/{task_id}/brief", response_model=TaskBriefResponse)
async def get_task_brief(task_id: str, request: Request) -> TaskBriefResponse:
    """获取简报内容。"""
    from pathlib import Path

    store: TaskStore = request.app.state.store
    task = await store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"任务尚未完成，当前状态: {task['status']}",
        )
    brief_path = task.get("brief_path")
    if not brief_path:
        raise HTTPException(status_code=404, detail="简报文件路径不存在")

    path = Path(brief_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="简报文件不存在")

    markdown = path.read_text(encoding="utf-8")
    return TaskBriefResponse(
        task_id=task_id,
        title=task.get("title"),
        markdown=markdown,
    )


async def run_pipeline_background(task_id: str, url: str, store: TaskStore) -> None:
    """后台执行 pipeline。"""
    from podlator.graph.builder import build_graph

    await store.update(task_id, status="running")
    graph = build_graph()

    initial_state: dict[str, Any] = {
        "task_id": task_id,
        "source_url": url,
        "status": "running",
        "current_node": "",
        "node_durations_ms": {},
        "total_cost_usd": 0.0,
    }

    try:
        final_state = await graph.ainvoke(initial_state)  # type: ignore[call-overload]
        await store.update(
            task_id,
            status="completed",
            title=final_state.get("title"),
            brief_path=final_state.get("output_path"),
            cost_usd=final_state.get("total_cost_usd", 0.0),
            duration_seconds=final_state.get("duration_seconds"),
        )
    except Exception as e:
        logger.error("pipeline_failed", task_id=task_id, error=str(e), exc_info=True)
        await store.update(task_id, status="failed", error_message=str(e))


def _to_response(record: dict[str, Any]) -> TaskResponse:
    """将数据库记录转为 API 响应模型。"""
    return TaskResponse(
        task_id=record["id"],
        source_url=record["source_url"],
        title=record.get("title"),
        status=record["status"],
        current_node=record.get("current_node"),
        error_message=record.get("error_message"),
        cost_usd=record["cost_usd"] or 0.0,
        created_at=record["created_at"],
        updated_at=record["updated_at"],
    )
