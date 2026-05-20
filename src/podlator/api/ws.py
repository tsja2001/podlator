"""WebSocket 日志推送。M0 占位。"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket

router = APIRouter()


@router.websocket("/ws/tasks/{task_id}/logs")
async def task_logs(websocket: WebSocket, task_id: str) -> None:
    """订阅任务实时日志。M0 占位：接受连接后发送一条测试消息。"""
    await websocket.accept()
    await websocket.send_json(
        {"event": "connected", "task_id": task_id, "message": "M0 placeholder"}
    )
    await websocket.close()
