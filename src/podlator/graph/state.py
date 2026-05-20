"""LangGraph 状态机核心数据结构。所有节点读写此 State。"""

from __future__ import annotations

from typing import TypedDict


class TranscriptSegment(TypedDict):
    """一条转写片段。"""

    text: str
    start: float
    end: float
    speaker: str | None
    confidence: float | None


class Chapter(TypedDict):
    """一个章节。"""

    index: int
    title: str
    start: float
    end: float
    segment_indices: list[int]
    summary_zh: str


class PodlatorState(TypedDict, total=False):
    """Pipeline 全局状态。节点返回 partial dict，LangGraph 自动合并。"""

    # ── 身份标识（创建时设定）──
    task_id: str
    source_url: str

    # ── 元数据（fetch_metadata 产出）──
    title: str
    description: str
    duration_seconds: float
    published_at: str
    source_type: str
    thumbnail_url: str

    # ── 音频（download_audio 产出）──
    audio_path: str
    audio_format: str
    audio_size_bytes: int

    # ── 转写（transcribe 产出）──
    transcript_segments: list[TranscriptSegment]
    transcript_text: str
    stt_provider: str
    has_diarization: bool

    # ── 章节（chapter_split 产出）──
    chapters: list[Chapter]

    # ── 摘要（summarize_chapters 产出）──
    chapter_summaries: list[str]

    # ── 简报（polish_final 产出）──
    brief_markdown: str

    # ── 导出（export_markdown 产出）──
    output_path: str

    # ── 控制字段 ──
    current_node: str
    status: str
    error: str | None
    node_durations_ms: dict[str, float]
    total_cost_usd: float
    created_at: str
    updated_at: str
