"""Graph 组装测试。"""

from __future__ import annotations

from podlator.graph.builder import build_graph


def test_build_graph_compiles() -> None:
    """Graph 能成功编译。"""
    g = build_graph()
    assert g is not None


def test_build_graph_has_all_8_nodes() -> None:
    """Graph 包含所有 8 个节点 + __start__。"""
    g = build_graph()
    expected = {
        "fetch_metadata",
        "download_audio",
        "transcribe",
        "diarize",
        "chapter_split",
        "summarize_chapters",
        "polish_final",
        "export_markdown",
        "__start__",
    }
    assert set(g.nodes.keys()) == expected
