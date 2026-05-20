"""Graph 集成测试。"""

from __future__ import annotations

import pytest

from podlator.graph.builder import build_graph


@pytest.mark.asyncio
async def test_graph_can_invoke_with_initial_state() -> None:
    """Graph 能在初始 state 上 ainvoke 并走完所有占位节点。"""
    g = build_graph()
    initial = {
        "task_id": "integration-test-001",
        "source_url": "https://example.com",
    }
    result = await g.ainvoke(initial)
    # M0 所有节点都是占位，但 Graph 应该能跑完
    assert result is not None
    assert "task_id" in result
    assert "current_node" in result
