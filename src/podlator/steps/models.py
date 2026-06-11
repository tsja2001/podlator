"""Step 文件格式模型。

定义 TranscriptDocument、ChapterDocument 等 Pydantic 模型，
确保 CLI、LangGraph、外部工具之间通过稳定的 JSON schema 交互。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# -- Transcript 相关模型 --


class TranscriptSource(BaseModel):
    """转录来源信息。"""

    audio_path: str | None = Field(default=None, description="原始音频文件路径")
    source_url: str | None = Field(default=None, description="原始 URL（如 YouTube）")
    title: str | None = Field(default=None, description="节目标题")
    duration_seconds: float | None = Field(default=None, description="音频时长（秒）")


class TranscriptProviderMeta(BaseModel):
    """转录服务提供者元信息。"""

    name: str = Field(description="Provider 名称，如 deepgram / tencent_cloud / srt")
    cost_usd: float = Field(default=0.0, description="转录费用（美元）")


class TranscriptSegmentModel(BaseModel):
    """单条转录片段。"""

    index: int = Field(description="片段序号，从 0 开始")
    start: float = Field(description="开始时间（秒）")
    end: float = Field(description="结束时间（秒）")
    text: str = Field(description="片段文本")
    speaker: str | None = Field(default=None, description="说话人标签")
    confidence: float | None = Field(default=None, description="置信度 (0.0-1.0)")


class TranscriptDocument(BaseModel):
    """完整的转录文档 — step 层的标准转录格式。"""

    schema_version: int = Field(default=1, description="JSON schema 版本号")
    source: TranscriptSource = Field(default_factory=TranscriptSource)
    provider: TranscriptProviderMeta = Field(
        default_factory=lambda: TranscriptProviderMeta(name="unknown")
    )
    text: str = Field(default="", description="完整转录文本")
    segments: list[TranscriptSegmentModel] = Field(
        default_factory=list, description="带时间戳的转录片段"
    )


# -- Chapter 相关模型 --


class ChapterModel(BaseModel):
    """单个章节。"""

    index: int = Field(description="章节序号，从 0 开始")
    title: str = Field(description="章节标题（中文）")
    start: float = Field(description="开始时间（秒）")
    end: float = Field(description="结束时间（秒）")
    segment_indices: list[int] = Field(
        default_factory=list, description="属于本章节的 transcript segment 序号"
    )


class ChapterDocument(BaseModel):
    """完整的章节文档 — step 层的标准章节格式。"""

    schema_version: int = Field(default=1, description="JSON schema 版本号")
    source_transcript: str | None = Field(
        default=None, description="来源 Transcript JSON 文件路径"
    )
    chapters: list[ChapterModel] = Field(default_factory=list, description="章节列表")


# -- Eval / Judge 相关模型（M5.1）--


class DimensionScore(BaseModel):
    """单一维度的评分结果。"""

    dimension: str
    score: float  # 信息覆盖度缺参照时为 -1（不计分标记）
    max_score: float
    evidence: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class RevisionDirective(BaseModel):
    """给写手的定点修订指令（M5.4 的修订循环将直接消费它）。"""

    target: str  # 定位描述，如「第二条 GPU 时间幻觉」一节
    problem: str
    instruction: str


class JudgeReport(BaseModel):
    """LLM judge 的完整评分报告。"""

    rubric_version: str
    total_score: float
    dimensions: list[DimensionScore]
    revision_directives: list[RevisionDirective] = Field(default_factory=list)
    verdict: Literal["pass", "needs_revision"]


class LintStats(BaseModel):
    """程序化文本统计（零 LLM 成本）。"""

    char_count: int  # 中文字数
    sentence_count: int
    long_sentence_ratio: float  # >40 字句子占比
    short_sentence_ratio: float  # <15 字句子占比
    interaction_density: float  # 互动词次数 / (字数/300)，即"每 300 字互动次数"
    markdown_heading_count: int  # ^#{1,6}\s 行数
    meta_text_detected: bool  # 开头是否命中 meta 模式
    speaker_label_count: int  # "Speaker A/B" / "说话人A" 残留次数
    truncation_suspected: bool  # 非空稿件结尾未落在终止符（。！？…」"）→ 疑似被截断
    word_count_target: int | None  # 目标字数（未知时 None）
    word_count_ok: bool | None  # 实际在目标 ±10% 内？（无目标时 None）
