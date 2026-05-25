"""LogHub 单元测试。"""

from __future__ import annotations

import pytest

from podlator.api.log_hub import LogHub


@pytest.fixture
def hub() -> LogHub:
    return LogHub(max_queue_size=3)


@pytest.mark.asyncio
async def test_publish_delivers_event_to_matching_task(hub: LogHub) -> None:
    """发布到匹配 task_id 的事件能被订阅者收到。"""
    async with hub.subscribe("task-1") as queue:
        await hub.publish({"task_id": "task-1", "event": "node_started"})
        await hub.publish({"task_id": "task-1", "event": "node_completed"})

        assert queue.qsize() == 2
        e1 = queue.get_nowait()
        assert e1["event"] == "node_started"
        e2 = queue.get_nowait()
        assert e2["event"] == "node_completed"


@pytest.mark.asyncio
async def test_publish_ignores_event_without_task_id(hub: LogHub) -> None:
    """无 task_id 的事件不被广播。"""
    async with hub.subscribe("task-1") as queue:
        await hub.publish({"event": "no_task_id", "msg": "hello"})
        assert queue.empty()


@pytest.mark.asyncio
async def test_subscribe_removes_queue_after_context_exit(hub: LogHub) -> None:
    """订阅退出后队列从 subscribers 中移除。"""
    async with hub.subscribe("task-1"):
        assert "task-1" in hub._subscribers
    # 退出后 clean
    assert "task-1" not in hub._subscribers


@pytest.mark.asyncio
async def test_publish_does_not_deliver_to_other_task(hub: LogHub) -> None:
    """不同 task_id 的事件不串流。"""
    async with hub.subscribe("task-1") as q1, hub.subscribe("task-2") as q2:
        await hub.publish({"task_id": "task-1", "event": "only_for_1"})
        assert q1.qsize() == 1
        assert q2.empty()


@pytest.mark.asyncio
async def test_queue_full_drops_oldest_event(hub: LogHub) -> None:
    """队列满时丢弃最旧事件。"""
    async with hub.subscribe("task-1") as queue:
        for i in range(5):
            await hub.publish({"task_id": "task-1", "event": f"evt_{i}"})
        # queue maxsize=3, 5 publishes, so only the last 3 should remain
        events = []
        while not queue.empty():
            events.append(queue.get_nowait()["event"])
        assert len(events) == 3
        assert "evt_2" in events
        assert "evt_3" in events
        assert "evt_4" in events


@pytest.mark.asyncio
async def test_multiple_subscribers_same_task(hub: LogHub) -> None:
    """同一 task_id 的多个订阅者都收到事件。"""
    async with hub.subscribe("task-1") as q1, hub.subscribe("task-1") as q2:
        await hub.publish({"task_id": "task-1", "event": "broadcast"})
        assert q1.qsize() == 1
        assert q2.qsize() == 1


@pytest.mark.asyncio
async def test_publish_ignores_non_string_task_id(hub: LogHub) -> None:
    """task_id 不是字符串时忽略。"""
    async with hub.subscribe("task-1") as queue:
        await hub.publish({"task_id": 123, "event": "bad"})
        assert queue.empty()
