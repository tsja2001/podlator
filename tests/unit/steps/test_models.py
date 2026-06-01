"""Unit tests for step models (models.py)."""

from __future__ import annotations

from podlator.steps.models import (
    ChapterDocument,
    ChapterModel,
    TranscriptDocument,
    TranscriptProviderMeta,
    TranscriptSegmentModel,
    TranscriptSource,
)


class TestTranscriptSource:
    def test_default_values(self) -> None:
        source = TranscriptSource()
        assert source.audio_path is None
        assert source.source_url is None
        assert source.title is None
        assert source.duration_seconds is None

    def test_full_initialization(self) -> None:
        source = TranscriptSource(
            audio_path="/tmp/audio.mp3",
            source_url="https://youtube.com/watch?v=xxx",
            title="Test Episode",
            duration_seconds=1234.5,
        )
        assert source.audio_path == "/tmp/audio.mp3"
        assert source.source_url == "https://youtube.com/watch?v=xxx"
        assert source.title == "Test Episode"
        assert source.duration_seconds == 1234.5


class TestTranscriptProviderMeta:
    def test_minimal_initialization(self) -> None:
        meta = TranscriptProviderMeta(name="deepgram")
        assert meta.name == "deepgram"
        assert meta.cost_usd == 0.0

    def test_with_cost(self) -> None:
        meta = TranscriptProviderMeta(name="tencent_cloud", cost_usd=0.005)
        assert meta.name == "tencent_cloud"
        assert meta.cost_usd == 0.005


class TestTranscriptSegmentModel:
    def test_full_initialization(self) -> None:
        seg = TranscriptSegmentModel(
            index=0,
            start=0.0,
            end=5.25,
            text="Welcome to the show.",
            speaker="speaker_0",
            confidence=0.98,
        )
        assert seg.index == 0
        assert seg.start == 0.0
        assert seg.end == 5.25
        assert seg.text == "Welcome to the show."
        assert seg.speaker == "speaker_0"
        assert seg.confidence == 0.98

    def test_speaker_can_be_none(self) -> None:
        seg = TranscriptSegmentModel(
            index=1, start=5.25, end=10.0, text="Hello.", speaker=None
        )
        assert seg.speaker is None

    def test_confidence_can_be_none(self) -> None:
        seg = TranscriptSegmentModel(
            index=0, start=0.0, end=1.0, text="Hi.", confidence=None
        )
        assert seg.confidence is None


class TestTranscriptDocument:
    def test_default_initialization(self) -> None:
        doc = TranscriptDocument()
        assert doc.schema_version == 1
        assert doc.source.audio_path is None
        assert doc.provider.name == "unknown"
        assert doc.text == ""
        assert doc.segments == []

    def test_full_initialization(self) -> None:
        source = TranscriptSource(title="Test", duration_seconds=60.0)
        provider = TranscriptProviderMeta(name="deepgram", cost_usd=0.01)
        segments = [
            TranscriptSegmentModel(index=0, start=0.0, end=2.0, text="Hi.", speaker="A")
        ]
        doc = TranscriptDocument(
            source=source, provider=provider, text="Hi.", segments=segments
        )
        assert doc.source.title == "Test"
        assert doc.provider.name == "deepgram"
        assert doc.provider.cost_usd == 0.01
        assert len(doc.segments) == 1
        assert doc.segments[0].text == "Hi."

    def test_serialization_roundtrip(self) -> None:
        """验证 model_dump + 重新构造可以无损往返。"""
        doc = TranscriptDocument(
            source=TranscriptSource(
                audio_path="/tmp/audio.mp3",
                source_url="https://example.com",
                title="Test",
                duration_seconds=100.0,
            ),
            provider=TranscriptProviderMeta(name="srt", cost_usd=0.0),
            text="Full text",
            segments=[
                TranscriptSegmentModel(
                    index=0, start=0.0, end=5.0, text="Hello.", speaker=None
                )
            ],
        )
        data = doc.model_dump()
        restored = TranscriptDocument(**data)
        assert restored.schema_version == doc.schema_version
        assert restored.source.title == doc.source.title
        assert restored.source.audio_path == doc.source.audio_path
        assert restored.provider.name == doc.provider.name
        assert len(restored.segments) == 1
        assert restored.segments[0].text == "Hello."


class TestChapterModel:
    def test_full_initialization(self) -> None:
        ch = ChapterModel(
            index=0,
            title="开场介绍",
            start=0.0,
            end=120.5,
            segment_indices=[0, 1, 2],
        )
        assert ch.index == 0
        assert ch.title == "开场介绍"
        assert ch.start == 0.0
        assert ch.end == 120.5
        assert ch.segment_indices == [0, 1, 2]

    def test_segment_indices_defaults_to_empty(self) -> None:
        ch = ChapterModel(index=0, title="Chapter", start=0.0, end=10.0)
        assert ch.segment_indices == []


class TestChapterDocument:
    def test_default_initialization(self) -> None:
        doc = ChapterDocument()
        assert doc.schema_version == 1
        assert doc.source_transcript is None
        assert doc.chapters == []

    def test_full_initialization(self) -> None:
        chapters = [
            ChapterModel(index=0, title="Ch1", start=0.0, end=10.0, segment_indices=[0])
        ]
        doc = ChapterDocument(source_transcript="transcript.json", chapters=chapters)
        assert doc.source_transcript == "transcript.json"
        assert len(doc.chapters) == 1
        assert doc.chapters[0].title == "Ch1"

    def test_serialization_roundtrip(self) -> None:
        """验证 model_dump + 重新构造可以无损往返。"""
        doc = ChapterDocument(
            source_transcript="transcript.json",
            chapters=[
                ChapterModel(
                    index=0,
                    title="开场",
                    start=0.0,
                    end=30.0,
                    segment_indices=[0, 1],
                ),
                ChapterModel(
                    index=1,
                    title="正文",
                    start=30.0,
                    end=60.0,
                    segment_indices=[2, 3],
                ),
            ],
        )
        data = doc.model_dump()
        restored = ChapterDocument(**data)
        assert restored.schema_version == doc.schema_version
        assert restored.source_transcript == "transcript.json"
        assert len(restored.chapters) == 2
        assert restored.chapters[0].title == "开场"
        assert restored.chapters[1].segment_indices == [2, 3]
