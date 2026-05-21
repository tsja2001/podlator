"""Smoke 测试：用真实 API 跑一次简短的完整 pipeline。

仅当 PODLATOR_RUN_SMOKE=1 时执行，会产生 API 费用（约 $0.02）。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from podlator.graph.builder import build_graph

pytestmark = pytest.mark.skipif(
    not os.getenv("PODLATOR_RUN_SMOKE"),
    reason="Smoke tests disabled (set PODLATOR_RUN_SMOKE=1 to enable)",
)

SHORT_VIDEO_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # "Me at the zoo" 19秒


@pytest.mark.asyncio
async def test_full_pipeline_real(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """真实 API 端到端测试（约 $0.01 - $0.05 费用）。"""
    from podlator.config import Settings

    # 使用临时目录避免污染真实数据
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))

    settings = Settings()
    # 确保路径指向 tmp_path
    settings.data_dir = tmp_path
    settings.database_path = str(tmp_path / "test.db")

    graph = build_graph()

    initial_state: dict = {
        "task_id": "smoke-test-001",
        "source_url": SHORT_VIDEO_URL,
        "status": "running",
        "current_node": "",
        "node_durations_ms": {},
        "total_cost_usd": 0.0,
    }

    result = await graph.ainvoke(initial_state)

    assert result.get("title"), "标题不应为空"
    assert result.get("transcript_text"), "转写文本不应为空"
    assert result.get("chapters"), "章节列表不应为空"
    assert result.get("brief_markdown"), "简报不应为空"

    # 简报应包含中文内容
    brief = result["brief_markdown"]
    has_chinese = any("一" <= c <= "鿿" for c in brief)
    assert has_chinese, "简报应包含中文内容"

    # 验证文件输出
    output_path = result.get("output_path", "")
    assert output_path, "输出路径不应为空"
    assert Path(output_path).exists(), f"输出文件不存在: {output_path}"

    # 验证费用
    cost = result.get("total_cost_usd", 0.0)
    assert cost > 0, f"费用应大于 0，实际: {cost}"
    print(f"\n  Smoke 测试费用: ${cost:.4f}")
    print(f"  标题: {result['title']}")
    print(f"  输出: {output_path}")
