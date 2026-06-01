"""Step 文件 I/O 层。

提供 TranscriptDocument、ChapterDocument 和 Markdown 的读写函数。
所有 JSON 输出使用 ensure_ascii=False + indent=2。
"""

from __future__ import annotations

import json
from pathlib import Path

from podlator.steps.models import ChapterDocument, TranscriptDocument


def read_transcript(path: Path) -> TranscriptDocument:
    """从 JSON 文件读取 TranscriptDocument。

    Args:
        path: Transcript JSON 文件路径。

    Returns:
        解析后的 TranscriptDocument。

    Raises:
        FileNotFoundError: 文件不存在。
        ValueError: JSON 格式不合法或 schema_version 不支持。
    """
    if not path.exists():
        raise FileNotFoundError(f"Transcript 文件不存在: {path}")

    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Transcript JSON 格式不合法 ({path}): {e}") from e

    schema_version = data.get("schema_version")
    if schema_version is not None and schema_version != 1:
        raise ValueError(
            f"Transcript schema_version 不支持: {schema_version}（仅支持 1）"
        )

    return TranscriptDocument(**data)


def write_transcript(path: Path, doc: TranscriptDocument) -> None:
    """将 TranscriptDocument 写入 JSON 文件。

    Args:
        path: 输出文件路径。
        doc: 要写入的 TranscriptDocument。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = doc.model_dump(exclude_none=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def read_chapters(path: Path) -> ChapterDocument:
    """从 JSON 文件读取 ChapterDocument。

    Args:
        path: Chapters JSON 文件路径。

    Returns:
        解析后的 ChapterDocument。

    Raises:
        FileNotFoundError: 文件不存在。
        ValueError: JSON 格式不合法或 schema_version 不支持。
    """
    if not path.exists():
        raise FileNotFoundError(f"Chapters 文件不存在: {path}")

    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Chapters JSON 格式不合法 ({path}): {e}") from e

    schema_version = data.get("schema_version")
    if schema_version is not None and schema_version != 1:
        raise ValueError(
            f"Chapters schema_version 不支持: {schema_version}（仅支持 1）"
        )

    return ChapterDocument(**data)


def write_chapters(path: Path, doc: ChapterDocument) -> None:
    """将 ChapterDocument 写入 JSON 文件。

    Args:
        path: 输出文件路径。
        doc: 要写入的 ChapterDocument。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = doc.model_dump(exclude_none=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def read_markdown(path: Path) -> str:
    """读取 Markdown 文件内容。

    Args:
        path: Markdown 文件路径。

    Returns:
        文件内容（字符串）。

    Raises:
        FileNotFoundError: 文件不存在。
    """
    if not path.exists():
        raise FileNotFoundError(f"Markdown 文件不存在: {path}")
    return path.read_text(encoding="utf-8")


def write_markdown(path: Path, content: str) -> None:
    """将内容写入 Markdown 文件。

    Args:
        path: 输出文件路径。
        content: Markdown 内容字符串。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
