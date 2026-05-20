"""REST API 路由。"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from podlator.api.schemas import (
    HealthResponse,
    TaskCreate,
    TaskResponse,
)
from podlator.storage.db import TaskStore

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """健康检查。"""
    return HealthResponse(status="ok")


@router.post("/tasks", status_code=201, response_model=TaskResponse)
async def create_task(body: TaskCreate, request: Request) -> TaskResponse:
    """创建新任务。"""
    store: TaskStore = request.app.state.store
    task_id = str(uuid.uuid4())
    record = await store.create(task_id, str(body.url))
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


@router.post("/tasks/{task_id}/retry", status_code=501)
async def retry_task(task_id: str) -> dict[str, str]:
    """重试失败任务。M0 占位。"""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/tasks/{task_id}/brief", status_code=501)
async def get_task_brief(task_id: str) -> dict[str, str]:
    """获取简报内容。M0 占位。"""
    raise HTTPException(status_code=501, detail="Not implemented")


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
