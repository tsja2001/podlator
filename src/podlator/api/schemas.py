"""Pydantic 请求/响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, HttpUrl


class TaskCreate(BaseModel):
    url: HttpUrl


class TaskResponse(BaseModel):
    task_id: str
    source_url: str
    title: str | None
    status: str
    current_node: str | None
    error_message: str | None
    cost_usd: float
    created_at: str
    updated_at: str


class TaskBriefResponse(BaseModel):
    task_id: str
    title: str | None
    markdown: str


class HealthResponse(BaseModel):
    status: str = "ok"
