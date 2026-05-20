"""TaskStore CRUD 测试。"""

from __future__ import annotations

import pytest

from podlator.storage.db import TaskStore


@pytest.fixture
async def store() -> TaskStore:
    """创建已初始化的 memory store。"""
    s = TaskStore(":memory:")
    await s.initialize()
    return s


@pytest.mark.asyncio
async def test_create_task(store: TaskStore) -> None:
    """创建任务后能查到。"""
    record = await store.create("t1", "https://example.com")
    assert record["id"] == "t1"
    assert record["status"] == "pending"
    assert record["source_url"] == "https://example.com"


@pytest.mark.asyncio
async def test_get_task(store: TaskStore) -> None:
    """能按 ID 查询任务。"""
    await store.create("t2", "https://example.com/2")
    record = await store.get("t2")
    assert record is not None
    assert record["id"] == "t2"


@pytest.mark.asyncio
async def test_get_nonexistent_task_returns_none(store: TaskStore) -> None:
    """查询不存在的任务返回 None。"""
    record = await store.get("no-such-id")
    assert record is None


@pytest.mark.asyncio
async def test_list_tasks(store: TaskStore) -> None:
    """能列表所有任务。"""
    await store.create("t3", "https://a.com")
    await store.create("t4", "https://b.com")
    tasks = await store.list_tasks()
    assert len(tasks) == 2


@pytest.mark.asyncio
async def test_list_tasks_filter_by_status(store: TaskStore) -> None:
    """能按状态过滤任务。"""
    await store.create("t5", "https://a.com")
    await store.update("t5", status="running")
    await store.create("t6", "https://b.com")
    running = await store.list_tasks(status="running")
    pending = await store.list_tasks(status="pending")
    assert len(running) == 1
    assert len(pending) == 1


@pytest.mark.asyncio
async def test_update_task(store: TaskStore) -> None:
    """能更新任务字段。"""
    await store.create("t7", "https://a.com")
    updated = await store.update("t7", status="running", current_node="fetch_metadata")
    assert updated["status"] == "running"
    assert updated["current_node"] == "fetch_metadata"


@pytest.mark.asyncio
async def test_delete_task(store: TaskStore) -> None:
    """能删除任务。"""
    await store.create("t8", "https://a.com")
    assert await store.delete("t8") is True
    assert await store.get("t8") is None


@pytest.mark.asyncio
async def test_delete_nonexistent_task_returns_false(store: TaskStore) -> None:
    """删除不存在的任务返回 False。"""
    assert await store.delete("no-such") is False
