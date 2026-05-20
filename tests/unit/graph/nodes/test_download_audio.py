"""download_audio 节点测试。"""

from __future__ import annotations

import inspect

import pytest

from podlator.graph.nodes.download_audio import run


@pytest.mark.asyncio
async def test_download_audio_returns_dict(sample_state: dict) -> None:
    """占位节点返回 dict。"""
    result = await run(sample_state)
    assert isinstance(result, dict)


def test_download_audio_is_async() -> None:
    """节点是异步函数。"""
    assert inspect.iscoroutinefunction(run)
