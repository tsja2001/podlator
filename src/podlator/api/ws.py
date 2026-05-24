"""WebSocket 日志推送。"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from podlator.api.log_hub import LogHub
from podlator.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.websocket("/ws/tasks/{task_id}/logs")
async def task_logs(websocket: WebSocket, task_id: str) -> None:
    """订阅任务实时日志。"""
    await websocket.accept()

    hub: LogHub = websocket.app.state.log_hub
    await websocket.send_json({"event": "connected", "task_id": task_id})
    logger.info("websocket_connected", task_id=task_id)

    try:
        async with hub.subscribe(task_id) as queue:
            while True:
                event = await queue.get()
                await websocket.send_json(event)
    except WebSocketDisconnect:
        logger.info("websocket_disconnected", task_id=task_id)
