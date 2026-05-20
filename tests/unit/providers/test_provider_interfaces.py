"""Provider 接口测试。"""

from __future__ import annotations

from podlator.graph.state import TranscriptSegment
from podlator.providers.downloader.base import (
    DownloaderProvider,
    DownloadResult,
    MediaMetadata,
)
from podlator.providers.llm.base import LLMProvider, LLMResult
from podlator.providers.stt.base import STTProvider, STTResult


def test_stt_result_creation() -> None:
    """STTResult 可用 dataclass 创建。"""
    seg: TranscriptSegment = {
        "text": "hello",
        "start": 0.0,
        "end": 0.5,
        "speaker": "SPEAKER_0",
        "confidence": 0.99,
    }
    r = STTResult(
        segments=[seg],
        full_text="hello",
        has_diarization=True,
        provider_name="deepgram",
        duration_ms=100.0,
        cost_usd=0.01,
    )
    assert r.provider_name == "deepgram"
    assert len(r.segments) == 1


def test_llm_result_creation() -> None:
    """LLMResult 可用 dataclass 创建。"""
    r = LLMResult(
        content="摘要内容",
        model="deepseek-v4-flash",
        provider_name="deepseek",
        tokens_in=100,
        tokens_out=50,
        duration_ms=500.0,
        cost_usd=0.002,
    )
    assert r.model == "deepseek-v4-flash"
    assert r.tokens_in == 100


def test_download_result_creation() -> None:
    """DownloadResult 可用 dataclass 创建。"""
    from pathlib import Path

    r = DownloadResult(
        file_path=Path("/tmp/test.mp3"),
        format="mp3",
        size_bytes=1024,
        duration_seconds=60.0,
    )
    assert r.format == "mp3"


def test_media_metadata_creation() -> None:
    """MediaMetadata 可用 dataclass 创建。"""
    m = MediaMetadata(
        title="Test Episode",
        description="A test podcast",
        duration_seconds=1800.0,
        published_at="2026-01-01T00:00:00Z",
        source_type="youtube",
        thumbnail_url="https://example.com/thumb.jpg",
    )
    assert m.title == "Test Episode"
    assert m.source_type == "youtube"


def test_stt_provider_is_abstract() -> None:
    """STTProvider 是抽象类，不能直接实例化。"""
    import inspect

    assert inspect.isabstract(STTProvider)


def test_llm_provider_is_abstract() -> None:
    """LLMProvider 是抽象类。"""
    import inspect

    assert inspect.isabstract(LLMProvider)


def test_downloader_provider_is_abstract() -> None:
    """DownloaderProvider 是抽象类。"""
    import inspect

    assert inspect.isabstract(DownloaderProvider)
