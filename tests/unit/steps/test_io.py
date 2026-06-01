"""Unit tests for step file I/O (io.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from podlator.steps.io import (
    read_chapters,
    read_markdown,
    read_transcript,
    write_chapters,
    write_markdown,
    write_transcript,
)
from podlator.steps.models import (
    ChapterDocument,
    ChapterModel,
    TranscriptDocument,
    TranscriptProviderMeta,
    TranscriptSegmentModel,
    TranscriptSource,
)


def _make_transcript() -> TranscriptDocument:
    """创建一个最小但有效的 TranscriptDocument fixture。"""
    return TranscriptDocument(
        source=TranscriptSource(
            audio_path="episode.mp3",
            title="Test Episode",
            duration_seconds=60.0,
        ),
        provider=TranscriptProviderMeta(name="deepgram", cost_usd=0.01),
        text="Hello world.",
        segments=[
            TranscriptSegmentModel(
                index=0, start=0.0, end=2.5, text="Hello world.", speaker="A"
            )
        ],
    )


def _make_chapters() -> ChapterDocument:
    """创建一个最小但有效的 ChapterDocument fixture。"""
    return ChapterDocument(
        source_transcript="transcript.json",
        chapters=[
            ChapterModel(index=0, title="开场", start=0.0, end=2.5, segment_indices=[0])
        ],
    )


class TestTranscriptIO:
    def test_write_and_read_roundtrip(self, tmp_path: Path) -> None:
        """正常路径：写入后读出，数据不变。"""
        doc = _make_transcript()
        filepath = tmp_path / "transcript.json"

        write_transcript(filepath, doc)
        restored = read_transcript(filepath)

        assert restored.schema_version == doc.schema_version
        assert restored.source.title == "Test Episode"
        assert restored.source.audio_path == "episode.mp3"
        assert restored.provider.name == "deepgram"
        assert restored.provider.cost_usd == 0.01
        assert restored.text == "Hello world."
        assert len(restored.segments) == 1
        assert restored.segments[0].text == "Hello world."

    def test_write_creates_parent_directories(self, tmp_path: Path) -> None:
        """验证 write 会自动创建父目录。"""
        doc = _make_transcript()
        filepath = tmp_path / "deep" / "nested" / "transcript.json"

        write_transcript(filepath, doc)
        assert filepath.exists()

    def test_write_json_format(self, tmp_path: Path) -> None:
        """验证 JSON 输出格式：ensure_ascii=False, indent=2, 中文不转义。"""
        doc = TranscriptDocument(
            source=TranscriptSource(title="测试标题"),
            provider=TranscriptProviderMeta(name="srt"),
            text="你好世界",
        )
        filepath = tmp_path / "transcript.json"
        write_transcript(filepath, doc)

        raw = filepath.read_text(encoding="utf-8")
        # 中文字符应当直接出现，而非 \uXXXX
        assert "测试标题" in raw
        assert "你好世界" in raw
        assert "\\u" not in raw

    def test_read_file_not_found(self, tmp_path: Path) -> None:
        """文件不存在时抛出 FileNotFoundError。"""
        filepath = tmp_path / "nonexistent.json"
        with pytest.raises(FileNotFoundError, match="Transcript 文件不存在"):
            read_transcript(filepath)

    def test_read_invalid_json(self, tmp_path: Path) -> None:
        """JSON 格式不合法时抛出 ValueError。"""
        filepath = tmp_path / "bad.json"
        filepath.write_text("{not valid json", encoding="utf-8")

        with pytest.raises(ValueError, match="Transcript JSON 格式不合法"):
            read_transcript(filepath)

    def test_read_unsupported_schema_version(self, tmp_path: Path) -> None:
        """不支持的 schema_version 抛出 ValueError。"""
        filepath = tmp_path / "transcript.json"
        filepath.write_text(
            json.dumps({"schema_version": 99, "source": {}, "provider": {"name": "x"}}),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="schema_version 不支持"):
            read_transcript(filepath)

    def test_read_no_schema_version_is_ok(self, tmp_path: Path) -> None:
        """没有 schema_version 字段时不报错（向后兼容）。"""
        doc = _make_transcript()
        data = doc.model_dump()
        del data["schema_version"]
        filepath = tmp_path / "transcript.json"
        filepath.write_text(json.dumps(data), encoding="utf-8")

        restored = read_transcript(filepath)
        assert restored.text == "Hello world."


class TestChapterIO:
    def test_write_and_read_roundtrip(self, tmp_path: Path) -> None:
        """正常路径：写入后读出，数据不变。"""
        doc = _make_chapters()
        filepath = tmp_path / "chapters.json"

        write_chapters(filepath, doc)
        restored = read_chapters(filepath)

        assert restored.schema_version == doc.schema_version
        assert restored.source_transcript == "transcript.json"
        assert len(restored.chapters) == 1
        assert restored.chapters[0].title == "开场"
        assert restored.chapters[0].segment_indices == [0]

    def test_write_creates_parent_directories(self, tmp_path: Path) -> None:
        """验证 write 会自动创建父目录。"""
        doc = _make_chapters()
        filepath = tmp_path / "deep" / "chapters.json"

        write_chapters(filepath, doc)
        assert filepath.exists()

    def test_read_file_not_found(self, tmp_path: Path) -> None:
        """文件不存在时抛出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError, match="Chapters 文件不存在"):
            read_chapters(Path("/nonexistent/chapters.json"))

    def test_read_invalid_json(self, tmp_path: Path) -> None:
        """JSON 格式不合法时抛出 ValueError。"""
        filepath = tmp_path / "bad.json"
        filepath.write_text("{invalid}", encoding="utf-8")

        with pytest.raises(ValueError, match="Chapters JSON 格式不合法"):
            read_chapters(filepath)

    def test_read_unsupported_schema_version(self, tmp_path: Path) -> None:
        """不支持的 schema_version 抛出 ValueError。"""
        filepath = tmp_path / "chapters.json"
        filepath.write_text(
            json.dumps({"schema_version": 999, "chapters": []}), encoding="utf-8"
        )

        with pytest.raises(ValueError, match="schema_version 不支持"):
            read_chapters(filepath)


class TestMarkdownIO:
    def test_write_and_read_roundtrip(self, tmp_path: Path) -> None:
        """正常路径：写入后读出，内容不变。"""
        content = "# Hello\n\n世界"
        filepath = tmp_path / "output.md"

        write_markdown(filepath, content)
        restored = read_markdown(filepath)

        assert restored == content

    def test_read_file_not_found(self, tmp_path: Path) -> None:
        """文件不存在时抛出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError, match="Markdown 文件不存在"):
            read_markdown(Path("/nonexistent/file.md"))

    def test_write_creates_parent_directories(self, tmp_path: Path) -> None:
        """验证 write 会自动创建父目录。"""
        filepath = tmp_path / "a" / "b" / "output.md"
        write_markdown(filepath, "# Test")
        assert filepath.exists()
