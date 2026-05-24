"""WebSocket 日志集成测试。WS 端到端通过手动联调验证。"""

from __future__ import annotations

import asyncio

import pytest

from podlator.api.log_hub import LogHub


@pytest.mark.asyncio
async def test_loghub_multiple_subscribers() -> None:
    """同一 task_id 的多个订阅者都能收到事件。"""
    hub = LogHub()

    async def subscriber(name: str) -> list[dict]:
        events: list[dict] = []
        async with hub.subscribe("task-1") as queue:
            await asyncio.sleep(0.01)
            evt = queue.get_nowait()
            events.append(evt)
        return events

    async with hub.subscribe("task-1") as q1, hub.subscribe("task-1") as q2:
        await hub.publish({"task_id": "task-1", "event": "test"})
        assert q1.qsize() == 1
        assert q2.qsize() == 1


@pytest.mark.asyncio
async def test_loghub_publish_after_disconnect_not_received() -> None:
    """订阅断开后不再收到事件。"""
    hub = LogHub()

    async with hub.subscribe("task-1") as queue:
        await hub.publish({"task_id": "task-1", "event": "first"})
        assert queue.qsize() == 1

    # 断开后 publish 不会报错，也不应投递
    await hub.publish({"task_id": "task-1", "event": "after_disconnect"})
    # 无订阅者时 publish 安静退出
    assert "task-1" not in hub._subscribers
