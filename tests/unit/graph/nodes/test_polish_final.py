"""polish_final 节点测试。"""

from __future__ import annotations

import inspect

import pytest

from podlator.graph.nodes.polish_final import run


@pytest.mark.asyncio
async def test_polish_final_returns_dict(sample_state: dict) -> None:
    """占位节点返回 dict。"""
    result = await run(sample_state)
    assert isinstance(result, dict)


def test_polish_final_is_async() -> None:
    """节点是异步函数。"""
    assert inspect.iscoroutinefunction(run)
