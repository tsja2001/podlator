"""transcribe 节点测试。"""

from __future__ import annotations

import inspect

import pytest

from podlator.graph.nodes.transcribe import run


@pytest.mark.asyncio
async def test_transcribe_returns_dict(sample_state: dict) -> None:
    """占位节点返回 dict。"""
    result = await run(sample_state)
    assert isinstance(result, dict)


def test_transcribe_is_async() -> None:
    """节点是异步函数。"""
    assert inspect.iscoroutinefunction(run)
