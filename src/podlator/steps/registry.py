"""Step Registry — 为后续 Workflow YAML 配置化预留接口。

注册格式: { name: { description, input_type, output_type } }
后续可通过 workflow YAML/JSON 配置按名称查找 step 并动态拼装。
"""

from __future__ import annotations

from dataclasses import dataclass

from podlator.steps.models import ChapterDocument, TranscriptDocument


@dataclass
class StepEntry:
    """单个 step 的注册信息。"""

    name: str
    description: str
    input_type: type
    output_type: type


_registry: dict[str, StepEntry] = {}


def register(
    name: str,
    description: str,
    input_type: type,
    output_type: type,
) -> None:
    """注册一个 step 到 registry。"""
    _registry[name] = StepEntry(
        name=name,
        description=description,
        input_type=input_type,
        output_type=output_type,
    )


def get_step(name: str) -> StepEntry:
    """按名称获取 step 注册信息。

    Raises:
        KeyError: 未注册的 step 名称。
    """
    if name not in _registry:
        available = ", ".join(sorted(_registry.keys()))
        raise KeyError(f"Unknown step: {name!r}. Available: {available}")
    return _registry[name]


def list_steps() -> dict[str, StepEntry]:
    """返回所有已注册 step 的副本。"""
    return dict(_registry)


# ── 注册所有步骤 ──

register(
    name="transcribe",
    description="音频文件 → Transcript JSON",
    input_type=str,  # audio file path
    output_type=TranscriptDocument,
)

register(
    name="parse_srt",
    description="SRT 字幕 → Transcript JSON",
    input_type=str,  # SRT file path
    output_type=TranscriptDocument,
)

register(
    name="assign_speakers",
    description="Transcript JSON → 带 speaker 的 Transcript JSON",
    input_type=TranscriptDocument,
    output_type=TranscriptDocument,
)

register(
    name="split",
    description="Transcript JSON → Chapters JSON",
    input_type=TranscriptDocument,
    output_type=ChapterDocument,
)

register(
    name="render",
    description="Transcript + Chapters → Markdown",
    input_type=TranscriptDocument,
    output_type=str,  # Markdown text
)

register(
    name="polish",
    description="Markdown 草稿 → 润色 Markdown",
    input_type=str,
    output_type=str,
)
