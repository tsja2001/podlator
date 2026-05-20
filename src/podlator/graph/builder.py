"""Graph 组装与编译。"""

from __future__ import annotations

from typing import Any

from langgraph.graph.state import CompiledStateGraph, StateGraph

from podlator.graph.nodes import (
    chapter_split,
    diarize,
    download_audio,
    export_markdown,
    fetch_metadata,
    polish_final,
    summarize_chapters,
    transcribe,
)
from podlator.graph.state import PodlatorState


def build_graph() -> CompiledStateGraph[
    PodlatorState, Any, PodlatorState, PodlatorState
]:
    """构建完整的 podlator pipeline Graph。

    M0 阶段：线性连接 8 个节点。M1 加入条件分支（has_diarization）。
    """
    workflow = StateGraph(PodlatorState)

    # 注册节点
    workflow.add_node("fetch_metadata", fetch_metadata.run)
    workflow.add_node("download_audio", download_audio.run)
    workflow.add_node("transcribe", transcribe.run)
    workflow.add_node("diarize", diarize.run)
    workflow.add_node("chapter_split", chapter_split.run)
    workflow.add_node("summarize_chapters", summarize_chapters.run)
    workflow.add_node("polish_final", polish_final.run)
    workflow.add_node("export_markdown", export_markdown.run)

    # 线性连接（M0 简化，暂不加入条件分支）
    workflow.set_entry_point("fetch_metadata")
    workflow.add_edge("fetch_metadata", "download_audio")
    workflow.add_edge("download_audio", "transcribe")
    # M1 加入条件分支: has_diarization → skip diarize
    workflow.add_edge("transcribe", "diarize")
    workflow.add_edge("diarize", "chapter_split")
    workflow.add_edge("chapter_split", "summarize_chapters")
    workflow.add_edge("summarize_chapters", "polish_final")
    workflow.add_edge("polish_final", "export_markdown")
    workflow.set_finish_point("export_markdown")

    return workflow.compile()
