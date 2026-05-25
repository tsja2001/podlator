"""任务日志广播中心。"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from podlator.logging import get_logger

logger = get_logger(__name__)


class LogHub:
    """按 task_id 把结构化日志广播给 WebSocket 订阅者。"""

    def __init__(self, max_queue_size: int = 500) -> None:
        self.max_queue_size = max_queue_size
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(
            set
        )

    @asynccontextmanager
    async def subscribe(
        self, task_id: str
    ) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=self.max_queue_size
        )
        self._subscribers[task_id].add(queue)
        logger.debug("subscriber_added", task_id=task_id)
        try:
            yield queue
        finally:
            self._subscribers[task_id].discard(queue)
            if not self._subscribers[task_id]:
                del self._subscribers[task_id]
            logger.debug("subscriber_removed", task_id=task_id)

    async def publish(self, event: dict[str, Any]) -> None:
        task_id = event.get("task_id")
        if not isinstance(task_id, str):
            return
        for queue in list(self._subscribers.get(task_id, ())):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                logger.warning("log_queue_full", task_id=task_id)
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("log_dropped", task_id=task_id)
