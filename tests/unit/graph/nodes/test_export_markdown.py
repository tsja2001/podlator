"""export_markdown 节点测试。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from podlator.graph.nodes.export_markdown import run


@pytest.fixture
def state() -> dict:
    return {
        "task_id": "test-task",
        "title": "Test Episode! With? Special: Chars",
        "brief_markdown": "# Test Episode\n\nTest content.",
    }


@pytest.mark.asyncio
async def test_export_creates_file(state: dict, tmp_path: Path) -> None:
    """导出创建 Markdown 文件，返回 output_path。"""
    fake_settings = type("obj", (), {"data_dir": tmp_path})()

    with patch(
        "podlator.graph.nodes.export_markdown.Settings",
        return_value=fake_settings,
    ):
        result = await run(state)

    assert result["output_path"]
    output = Path(result["output_path"])
    assert output.exists()
    content = output.read_text()
    assert "Test Episode" in content


@pytest.mark.asyncio
async def test_export_empty_brief() -> None:
    """空 brief 返回空 output_path。"""
    result = await run(
        {
            "task_id": "test",
            "brief_markdown": "",
            "title": "test",
        }
    )
    assert result["output_path"] == ""
