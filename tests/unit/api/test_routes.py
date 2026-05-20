"""API 路由测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from podlator.api.main import app
from podlator.storage.db import TaskStore


@pytest.fixture
async def client(tmp_path: Path) -> AsyncClient:
    """创建测试客户端，使用临时数据库。"""
    db_path = str(tmp_path / "test.db")
    store = TaskStore(db_path)
    await store.initialize()

    # 注入到 app state
    app.state.store = store
    app.state.settings = type("obj", (), {"data_dir": tmp_path, "log_dir": tmp_path})()
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    """健康检查返回 ok。"""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_create_task(client: AsyncClient) -> None:
    """创建任务返回 201。"""
    resp = await client.post("/api/tasks", json={"url": "https://example.com"})
    assert resp.status_code == 201
    data = resp.json()
    assert "task_id" in data
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_list_tasks(client: AsyncClient) -> None:
    """列出任务返回列表。"""
    await client.post("/api/tasks", json={"url": "https://a.com"})
    resp = await client.get("/api/tasks")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1


@pytest.mark.asyncio
async def test_get_task_not_found(client: AsyncClient) -> None:
    """不存在的任务返回 404。"""
    resp = await client.get("/api/tasks/nonexistent")
    assert resp.status_code == 404
