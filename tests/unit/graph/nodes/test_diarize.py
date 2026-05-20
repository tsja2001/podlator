"""diarize 节点测试。"""

from __future__ import annotations

import pytest

from podlator.graph.nodes.diarize import run


@pytest.mark.asyncio
async def test_diarize_skips_when_has_diarization() -> None:
    """已有说话人标签时跳过，返回仅含控制字段。"""
    result = await run(
        {
            "task_id": "test",
            "has_diarization": True,
        }
    )
    assert result.get("current_node") == "diarize"


@pytest.mark.asyncio
async def test_diarize_warns_when_not_implemented() -> None:
    """无标签时发出警告但不失败。"""
    result = await run(
        {
            "task_id": "test",
            "has_diarization": False,
        }
    )
    assert result.get("current_node") == "diarize"
    # 没有业务数据返回
    assert "transcript_segments" not in result
