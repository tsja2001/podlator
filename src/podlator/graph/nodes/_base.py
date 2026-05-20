"""节点装饰器和工具函数。"""

from __future__ import annotations

import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from podlator.errors import NodeError
from podlator.logging import get_logger


def node_logger(state: Any, node_name: str) -> Any:
    """返回绑定了 task_id 和 node 上下文的 structlog logger。"""
    task_id = state.get("task_id", "unknown") if hasattr(state, "get") else "unknown"
    return get_logger(f"podlator.node.{node_name}").bind(
        task_id=task_id, node=node_name
    )


def node(node_name: str) -> Callable[..., Any]:
    """装饰器：自动注入计时、日志、异常包装。

    被装饰的 async 函数应签名为：
        async def run(state: PodlatorState) -> dict[str, Any]:

    装饰器自动：
    - 设置 state["current_node"] = node_name
    - 记录 node_started / node_completed 日志
    - 记录耗时到 node_durations_ms
    - 捕获异常，包装为 NodeError，记录 node_failed 日志
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(state: Any) -> dict[str, Any]:
            log = node_logger(state, node_name)
            log.info("node_started")

            start = time.monotonic()
            try:
                result = await func(state)
            except NodeError:
                raise
            except Exception as e:
                log.error(
                    "node_failed",
                    error_type=type(e).__name__,
                    error_msg=str(e),
                    retryable=False,
                    exc_info=True,
                )
                raise NodeError(node_name, str(e), retryable=False) from e

            duration_ms = (time.monotonic() - start) * 1000

            patch: dict[str, Any] = {
                "current_node": node_name,
                "node_durations_ms": {node_name: duration_ms},
            }

            if isinstance(result, dict):
                patch.update(result)

            log.info(
                "node_completed",
                duration_ms=duration_ms,
                produced=list(result.keys()) if isinstance(result, dict) else [],
            )
            return patch

        return wrapper

    return decorator
