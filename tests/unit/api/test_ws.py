"""WebSocket 日志订阅测试。"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from podlator.api.log_hub import LogHub
from podlator.api.main import app
from podlator.storage.db import TaskStore


def _run_async(coro):
    """在 sync 测试中运行 async 代码。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def ws_test_client(tmp_path: Path) -> TestClient:
    """创建带 LogHub 的测试客户端（同步 TestClient）。"""
    db_path = str(tmp_path / "test.db")

    async def _init() -> None:
        store = TaskStore(db_path)
        await store.initialize()
        app.state.store = store
        app.state.settings = type(
            "obj", (), {"data_dir": tmp_path, "log_dir": tmp_path}
        )()
        app.state.log_hub = LogHub()

    _run_async(_init())
    return TestClient(app)


def test_websocket_receives_connected(ws_test_client: TestClient) -> None:
    """WebSocket 连接后收到 connected 事件。"""
    with ws_test_client.websocket_connect("/ws/tasks/task-1/logs") as ws:
        data = ws.receive_json()
        assert data["event"] == "connected"
        assert data["task_id"] == "task-1"


def test_websocket_receives_published_event(ws_test_client: TestClient) -> None:
    """向 hub 发布事件后 WebSocket 收到该事件。"""
    hub: LogHub = app.state.log_hub
    with ws_test_client.websocket_connect("/ws/tasks/task-1/logs") as ws:
        # 跳过 connected 帧
        ws.receive_json()

        _run_async(
            hub.publish(
                {
                    "task_id": "task-1",
                    "event": "node_started",
                    "node": "fetch_metadata",
                }
            )
        )

        event = ws.receive_json()
        assert event["event"] == "node_started"
        assert event["task_id"] == "task-1"


def test_websocket_no_cross_talk(ws_test_client: TestClient) -> None:
    """另一 task_id 的事件不串流到本连接。"""
    hub: LogHub = app.state.log_hub
    with (
        ws_test_client.websocket_connect("/ws/tasks/task-a/logs") as ws_a,
        ws_test_client.websocket_connect("/ws/tasks/task-b/logs") as ws_b,
    ):
        # 跳过 connected 帧
        ws_a.receive_json()
        ws_b.receive_json()

        _run_async(hub.publish({"task_id": "task-a", "event": "only_for_a"}))

        event_a = ws_a.receive_json()
        assert event_a["event"] == "only_for_a"
