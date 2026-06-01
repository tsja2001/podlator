"""Unit tests for parse_srt step."""

from __future__ import annotations

from pathlib import Path

import pytest

from podlator.steps.parse_srt import (
    _parse_srt_blocks,
    _timestamp_to_seconds,
    parse_srt_file,
    parse_srt_to_file,
)

SAMPLE_SRT = """1
00:00:00,000 --> 00:00:02,500
Welcome to the show.

2
00:00:02,500 --> 00:00:05,000
Today we discuss AI.

3
00:00:05,000 --> 00:00:10,000
Hello everyone.
Thanks for joining us.
"""


class TestTimestampToSeconds:
    def test_basic(self) -> None:
        assert _timestamp_to_seconds("00:00:00,000") == 0.0

    def test_with_seconds(self) -> None:
        assert _timestamp_to_seconds("00:00:05,250") == 5.25

    def test_with_minutes(self) -> None:
        assert _timestamp_to_seconds("00:01:30,000") == 90.0

    def test_with_hours(self) -> None:
        assert _timestamp_to_seconds("01:00:00,000") == 3600.0

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid SRT timestamp"):
            _timestamp_to_seconds("not a timestamp")


class TestParseSrtBlocks:
    def test_parses_valid_srt(self) -> None:
        blocks = _parse_srt_blocks(SAMPLE_SRT)
        assert len(blocks) == 3
        assert blocks[0]["index"] == 0
        assert blocks[0]["start"] == 0.0
        assert blocks[0]["end"] == 2.5
        assert blocks[0]["text"] == "Welcome to the show."

    def test_multiline_subtitle(self) -> None:
        blocks = _parse_srt_blocks(SAMPLE_SRT)
        # Block 3 has multiline text
        assert blocks[2]["text"] == "Hello everyone.\nThanks for joining us."

    def test_empty_content(self) -> None:
        blocks = _parse_srt_blocks("")
        assert blocks == []

    def test_timestamps_increasing(self) -> None:
        blocks = _parse_srt_blocks(SAMPLE_SRT)
        for i in range(1, len(blocks)):
            assert blocks[i]["start"] >= blocks[i - 1]["end"] - 0.1


class TestParseSrtFile:
    def test_parses_srt_to_transcript(self, tmp_path: Path) -> None:
        srt_path = tmp_path / "test.srt"
        srt_path.write_text(SAMPLE_SRT, encoding="utf-8")

        doc = parse_srt_file(srt_path, title="Test Podcast")

        assert doc.provider.name == "srt"
        assert doc.provider.cost_usd == 0.0
        assert doc.source.title == "Test Podcast"
        assert len(doc.segments) == 3
        assert doc.segments[0].text == "Welcome to the show."
        assert doc.segments[0].speaker is None
        assert doc.segments[0].start == 0.0
        assert doc.segments[0].end == 2.5
        # 全文本包含所有字幕
        assert "Welcome to the show" in doc.text
        assert "Today we discuss AI" in doc.text

    def test_with_source_url(self, tmp_path: Path) -> None:
        srt_path = tmp_path / "test.srt"
        srt_path.write_text(SAMPLE_SRT, encoding="utf-8")

        doc = parse_srt_file(srt_path, source_url="https://example.com")
        assert doc.source.source_url == "https://example.com"

    def test_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="SRT 文件不存在"):
            parse_srt_file(tmp_path / "nonexistent.srt")

    def test_empty_srt_raises(self, tmp_path: Path) -> None:
        srt_path = tmp_path / "empty.srt"
        srt_path.write_text("", encoding="utf-8")

        with pytest.raises(ValueError, match="SRT 文件为空"):
            parse_srt_file(srt_path)

    def test_all_segments_have_none_speaker(self, tmp_path: Path) -> None:
        """验证 parse-srt 默认 speaker 为 None，不调用 LLM。"""
        srt_path = tmp_path / "test.srt"
        srt_path.write_text(SAMPLE_SRT, encoding="utf-8")

        doc = parse_srt_file(srt_path)
        for seg in doc.segments:
            assert seg.speaker is None, f"Segment {seg.index} speaker should be None"

    def test_duration_from_last_segment(self, tmp_path: Path) -> None:
        srt_path = tmp_path / "test.srt"
        srt_path.write_text(SAMPLE_SRT, encoding="utf-8")

        doc = parse_srt_file(srt_path)
        assert doc.source.duration_seconds == 10.0


class TestParseSrtToFile:
    def test_writes_transcript_json(self, tmp_path: Path) -> None:
        srt_path = tmp_path / "test.srt"
        srt_path.write_text(SAMPLE_SRT, encoding="utf-8")
        out_path = tmp_path / "transcript.json"

        doc = parse_srt_to_file(srt_path, out_path, title="Test")

        assert out_path.exists()
        assert doc.source.title == "Test"
