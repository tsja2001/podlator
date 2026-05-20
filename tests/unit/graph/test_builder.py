"""Graph 组装测试。"""

from __future__ import annotations

from podlator.graph.builder import _should_diarize, build_graph


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


def test_should_diarize_skip_when_true() -> None:
    """has_diarization=True 时返回 chapter_split（跳过 diarize）。"""
    result = _should_diarize({"has_diarization": True})
    assert result == "chapter_split"


def test_should_diarize_run_when_false() -> None:
    """has_diarization=False 时返回 diarize。"""
    result = _should_diarize({"has_diarization": False})
    assert result == "diarize"


def test_should_diarize_default_when_missing() -> None:
    """has_diarization 未设置时默认需要 diarize。"""
    result = _should_diarize({})
    assert result == "diarize"
