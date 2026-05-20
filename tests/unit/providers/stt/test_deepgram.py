"""DeepgramProvider 单元测试。"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from podlator.errors import ProviderError
from podlator.providers.stt.deepgram import DeepgramProvider

DEEPGRAM_URL_PATTERN = re.compile(r"https://api\.deepgram\.com/v1/listen")


@pytest.fixture
def provider() -> DeepgramProvider:
    return DeepgramProvider(api_key="test-key", model="nova-3")


@pytest.fixture
def sample_audio(tmp_path: Path) -> Path:
    """创建一个小的假音频文件。"""
    p = tmp_path / "test.mp3"
    p.write_bytes(b"\x00" * 16000)
    return p


@pytest.fixture
def deepgram_fixture() -> dict:
    """加载 mock 响应。"""
    fixture_path = (
        Path(__file__).parent.parent.parent.parent
        / "fixtures"
        / "responses"
        / "deepgram_response.json"
    )
    return json.loads(fixture_path.read_text())


@pytest.mark.asyncio
async def test_transcribe_success(
    provider: DeepgramProvider,
    sample_audio: Path,
    deepgram_fixture: dict,
    httpx_mock: HTTPXMock,
) -> None:
    """正常转写返回正确的 segments。"""
    httpx_mock.add_response(
        url=DEEPGRAM_URL_PATTERN,
        method="POST",
        json=deepgram_fixture,
        status_code=200,
    )

    result = await provider.transcribe(sample_audio, diarize=True)

    assert len(result.segments) > 0
    assert result.full_text
    assert result.provider_name == "deepgram"
    assert result.has_diarization
    assert result.cost_usd > 0
    assert result.duration_ms > 0


@pytest.mark.asyncio
async def test_transcribe_with_diarization(
    provider: DeepgramProvider,
    sample_audio: Path,
    deepgram_fixture: dict,
    httpx_mock: HTTPXMock,
) -> None:
    """带说话人分离的转写，验证 segments 含 speaker。"""
    httpx_mock.add_response(
        url=DEEPGRAM_URL_PATTERN,
        method="POST",
        json=deepgram_fixture,
        status_code=200,
    )

    result = await provider.transcribe(sample_audio, diarize=True)

    assert result.has_diarization
    speakers = {s.get("speaker") for s in result.segments}
    assert len(speakers) >= 1


@pytest.mark.asyncio
async def test_transcribe_api_error(
    provider: DeepgramProvider,
    sample_audio: Path,
    httpx_mock: HTTPXMock,
) -> None:
    """API 返回 401 抛出 ProviderError(retryable=False)。"""
    httpx_mock.add_response(
        url=DEEPGRAM_URL_PATTERN,
        method="POST",
        json={"error": "Unauthorized"},
        status_code=401,
    )

    with pytest.raises(ProviderError) as exc_info:
        await provider.transcribe(sample_audio)

    assert exc_info.value.retryable is False


@pytest.mark.asyncio
async def test_transcribe_rate_limit(
    provider: DeepgramProvider,
    sample_audio: Path,
    httpx_mock: HTTPXMock,
) -> None:
    """API 返回 429 抛出 ProviderError(retryable=True)。"""
    httpx_mock.add_response(
        url=DEEPGRAM_URL_PATTERN,
        method="POST",
        status_code=429,
    )

    with pytest.raises(ProviderError) as exc_info:
        await provider.transcribe(sample_audio)

    assert exc_info.value.retryable is True


@pytest.mark.asyncio
async def test_transcribe_missing_file(provider: DeepgramProvider) -> None:
    """音频文件不存在抛出 ProviderError(retryable=False)。"""
    with pytest.raises(ProviderError) as exc_info:
        await provider.transcribe(Path("/nonexistent/audio.mp3"))

    assert exc_info.value.retryable is False
