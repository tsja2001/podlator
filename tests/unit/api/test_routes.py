"""API 路由测试。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from podlator.api.main import app
from podlator.storage.db import TaskStore


@pytest.fixture
def mock_pipeline() -> AsyncMock:
    """返回 run_pipeline_background 的 AsyncMock 供验证调用。"""
    with patch(
        "podlator.api.routes.run_pipeline_background",
        new_callable=AsyncMock,
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def _mock_background_pipeline(mock_pipeline: AsyncMock) -> None:
    """自动 mock 后台 pipeline，防止测试触发真实 pipeline。"""
    # mock_pipeline fixture 已经完成 patch，此 fixture 只做 autouse 触发
    pass


@pytest.fixture
async def client(tmp_path: Path) -> AsyncClient:
    """创建测试客户端，使用临时数据库。"""
    db_path = str(tmp_path / "test.db")
    store = TaskStore(db_path)
    await store.initialize()

    app.state.store = store
    app.state.settings = type("obj", (), {"data_dir": tmp_path, "log_dir": tmp_path})()
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ── 健康检查 ──


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    """健康检查返回 ok。"""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ── 创建任务 ──


@pytest.mark.asyncio
async def test_create_task(client: AsyncClient) -> None:
    """创建任务返回 201，状态为 pending。"""
    resp = await client.post("/api/tasks", json={"url": "https://a.com"})
    assert resp.status_code == 201
    data = resp.json()
    assert "task_id" in data
    assert data["status"] == "pending"
    assert "a.com" in data["source_url"]


@pytest.mark.asyncio
async def test_create_task_schedules_background_pipeline(
    client: AsyncClient, mock_pipeline: AsyncMock
) -> None:
    """创建任务后将 pipeline 加入后台任务。"""
    resp = await client.post("/api/tasks", json={"url": "https://example.com"})
    assert resp.status_code == 201
    task_id = resp.json()["task_id"]
    # 等一小会儿让后台任务执行
    import asyncio

    await asyncio.sleep(0.05)
    mock_pipeline.assert_called_once()
    call_args = mock_pipeline.call_args
    assert call_args.args[0] == task_id
    assert "example.com" in call_args.args[1]


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


# ── 删除任务 ──


@pytest.mark.asyncio
async def test_delete_task(client: AsyncClient) -> None:
    """删除存在的任务返回 204。"""
    resp = await client.post("/api/tasks", json={"url": "https://example.com"})
    task_id = resp.json()["task_id"]

    resp = await client.delete(f"/api/tasks/{task_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_task_not_found(client: AsyncClient) -> None:
    """删除不存在的任务返回 404。"""
    resp = await client.delete("/api/tasks/nonexistent")
    assert resp.status_code == 404


# ── 重试任务 ──


@pytest.mark.asyncio
async def test_retry_failed_task(client: AsyncClient) -> None:
    """重试失败任务应将状态重置为 pending。"""
    # 手动创建一个 failed 状态的任务
    store: TaskStore = app.state.store
    await store.create("task-001", "https://example.com")
    await store.update("task-001", status="failed", error_message="test error")

    resp = await client.post("/api/tasks/task-001/retry")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data.get("error_message") is None


@pytest.mark.asyncio
async def test_retry_non_failed_task_returns_409(client: AsyncClient) -> None:
    """重试非 failed 状态的任务返回 409。"""
    store: TaskStore = app.state.store
    await store.create("task-002", "https://example.com")

    resp = await client.post("/api/tasks/task-002/retry")
    assert resp.status_code == 409
    assert "只能重试失败任务" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_retry_task_not_found(client: AsyncClient) -> None:
    """重试不存在的任务返回 404。"""
    resp = await client.post("/api/tasks/nonexistent/retry")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_retry_failed_task_schedules_pipeline(
    client: AsyncClient, mock_pipeline: AsyncMock
) -> None:
    """重试失败任务应将 pipeline 加入后台任务。"""
    import asyncio

    store: TaskStore = app.state.store
    await store.create("task-retry-schedule", "https://example.com")
    await store.update("task-retry-schedule", status="failed", error_message="err")

    mock_pipeline.reset_mock()
    resp = await client.post("/api/tasks/task-retry-schedule/retry")
    assert resp.status_code == 200

    await asyncio.sleep(0.05)
    mock_pipeline.assert_called_once()
    assert mock_pipeline.call_args.args[0] == "task-retry-schedule"


# ── 获取简报 ──


@pytest.mark.asyncio
async def test_get_brief_success(client: AsyncClient, tmp_path: Path) -> None:
    """获取已完成任务的简报。"""
    store: TaskStore = app.state.store
    await store.create("task-003", "https://example.com")

    # 写入简报文件
    brief_path = tmp_path / "brief.md"
    brief_path.write_text("# Test Brief\n\n中文内容。", encoding="utf-8")

    await store.update(
        "task-003",
        status="completed",
        brief_path=str(brief_path),
        title="Test",
    )

    resp = await client.get("/api/tasks/task-003/brief")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == "task-003"
    assert data["title"] == "Test"
    assert "中文内容" in data["markdown"]


@pytest.mark.asyncio
async def test_get_brief_not_completed(client: AsyncClient) -> None:
    """未完成任务获取简报返回 400。"""
    store: TaskStore = app.state.store
    await store.create("task-004", "https://example.com")

    resp = await client.get("/api/tasks/task-004/brief")
    assert resp.status_code == 400
    assert "尚未完成" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_brief_task_not_found(client: AsyncClient) -> None:
    """获取不存在任务的简报返回 404。"""
    resp = await client.get("/api/tasks/nonexistent/brief")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_brief_file_missing(client: AsyncClient) -> None:
    """简报文件缺失时返回 404。"""
    store: TaskStore = app.state.store
    await store.create("task-005", "https://example.com")
    await store.update(
        "task-005",
        status="completed",
        brief_path="/nonexistent/path.md",
    )

    resp = await client.get("/api/tasks/task-005/brief")
    assert resp.status_code == 404


# ── 分页与过滤 ──


@pytest.mark.asyncio
async def test_list_tasks_with_status_filter(client: AsyncClient) -> None:
    """按状态过滤任务列表。"""
    store: TaskStore = app.state.store
    await store.create("t1", "https://a.com")
    await store.create("t2", "https://b.com")
    await store.update("t1", status="completed")

    resp = await client.get("/api/tasks?status=completed")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["task_id"] == "t1"


@pytest.mark.asyncio
async def test_list_tasks_pagination(client: AsyncClient) -> None:
    """分页参数正确生效。"""
    store: TaskStore = app.state.store
    for i in range(3):
        await store.create(f"t{i}", f"https://example.com/{i}")

    resp = await client.get("/api/tasks?limit=2&offset=0")
    assert resp.status_code == 200
    assert len(resp.json()) == 2
