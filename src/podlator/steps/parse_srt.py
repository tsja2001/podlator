"""Step: SRT 字幕文件 → Transcript JSON。

纯解析，不调用 LLM，不推断说话人。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from podlator.steps.io import write_transcript
from podlator.steps.models import (
    TranscriptDocument,
    TranscriptProviderMeta,
    TranscriptSegmentModel,
    TranscriptSource,
)

# SRT block: 序号, 时间行 "HH:MM:SS,mmm --> HH:MM:SS,mmm", 一行或多行字幕文本
_SRT_TIME_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})")


def _timestamp_to_seconds(timestamp: str) -> float:
    """将 SRT 时间戳 (HH:MM:SS,mmm) 转为秒。"""
    m = _SRT_TIME_RE.match(timestamp)
    if not m:
        raise ValueError(f"Invalid SRT timestamp: {timestamp!r}")
    h, mi, s, ms = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
    return h * 3600 + mi * 60 + s + ms / 1000


def _parse_srt_blocks(content: str) -> list[dict[str, Any]]:
    """解析 SRT 内容，返回 [{index, start, end, text}] 列表。

    Args:
        content: SRT 文件完整内容。

    Returns:
        解析后的 block 列表。

    Raises:
        ValueError: 时间格式非法（带 block 序号）。
    """
    blocks: list[dict[str, Any]] = []
    # 按空行分割 SRT blocks
    raw_blocks = re.split(r"\n\s*\n", content.strip())

    for raw in raw_blocks:
        raw = raw.strip()
        if not raw:
            continue

        lines = raw.split("\n")
        if len(lines) < 2:
            continue

        # 第 0 行: 序号（可忽略）
        # 第 1 行: 时间范围
        # 第 2+ 行: 字幕文本
        try:
            index = int(lines[0].strip())
        except ValueError:
            # 有些 SRT 的序号行可能出现非数字，跳过该 block
            continue

        time_line = lines[1].strip()
        time_parts = time_line.split("-->")
        if len(time_parts) != 2:
            raise ValueError(f"Block {index}: invalid time line: {time_line!r}")

        try:
            start = _timestamp_to_seconds(time_parts[0].strip())
            end = _timestamp_to_seconds(time_parts[1].strip())
        except ValueError as e:
            raise ValueError(f"Block {index}: {e}") from e

        text = "\n".join(lines[2:]).strip()
        blocks.append({"index": index - 1, "start": start, "end": end, "text": text})

    return blocks


def parse_srt_file(
    srt_path: Path,
    *,
    source_url: str | None = None,
    title: str | None = None,
) -> TranscriptDocument:
    """解析 SRT 字幕文件为 TranscriptDocument。

    行为：
    - 解析标准 SRT block（序号 / 时间 / 文本）。
    - 合并同一 block 的多行字幕文本。
    - speaker 默认 None。
    - provider.name = "srt"，cost_usd = 0.0。
    - 不调用 LLM，不做说话人推断。

    Args:
        srt_path: SRT 文件路径。
        source_url: 来源 URL（可选）。
        title: 节目标题（可选）。

    Returns:
        TranscriptDocument。

    Raises:
        FileNotFoundError: SRT 文件不存在。
        ValueError: SRT 为空或时间格式非法。
    """
    if not srt_path.exists():
        raise FileNotFoundError(f"SRT 文件不存在: {srt_path}")

    content = srt_path.read_text(encoding="utf-8")
    if not content.strip():
        raise ValueError(f"SRT 文件为空: {srt_path}")

    blocks = _parse_srt_blocks(content)
    if not blocks:
        raise ValueError(f"SRT 文件未解析出有效字幕: {srt_path}")

    segments = [
        TranscriptSegmentModel(
            index=b["index"],
            start=b["start"],
            end=b["end"],
            text=b["text"],
            speaker=None,
        )
        for b in blocks
    ]

    full_text = " ".join(seg.text for seg in segments)
    duration = segments[-1].end if segments else None

    doc = TranscriptDocument(
        source=TranscriptSource(
            audio_path=None,
            source_url=source_url,
            title=title,
            duration_seconds=duration,
        ),
        provider=TranscriptProviderMeta(name="srt", cost_usd=0.0),
        text=full_text,
        segments=segments,
    )
    return doc


def parse_srt_to_file(
    srt_path: Path,
    output_path: Path,
    *,
    source_url: str | None = None,
    title: str | None = None,
) -> TranscriptDocument:
    """解析 SRT 文件并直接写入 Transcript JSON。

    Args:
        srt_path: SRT 文件路径。
        output_path: 输出 JSON 路径。
        source_url: 来源 URL（可选）。
        title: 节目标题（可选）。

    Returns:
        TranscriptDocument。
    """
    doc = parse_srt_file(srt_path, source_url=source_url, title=title)
    write_transcript(output_path, doc)
    return doc
