"""TencentCloudProvider 单元测试。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from tencentcloud.common.exception.tencent_cloud_sdk_exception import (  # type: ignore[import-untyped]
    TencentCloudSDKException,
)

from podlator.errors import ProviderError
from podlator.providers.stt.tencent_cloud import (
    TencentCloudProvider,
    parse_task_status,
)


class FakeCosStorage:
    def __init__(self) -> None:
        self.delete_after_transcribe = True
        self.uploaded_paths: list[Path] = []
        self.deleted_keys: list[str] = []

    async def upload_and_presign(
        self, audio_path: Path, *, task_id: str | None = None
    ) -> tuple[str, str]:
        del task_id
        self.uploaded_paths.append(audio_path)
        return "podlator/asr-audio/test/audio.mp3", "https://cos.example.com/audio.mp3"

    async def delete(self, object_key: str) -> None:
        self.deleted_keys.append(object_key)


class FakeAsrClient:
    def __init__(
        self, statuses: list[Any], *, create_error: Exception | None = None
    ) -> None:
        self.statuses = statuses
        self.create_error = create_error
        self.create_requests: list[Any] = []
        self.describe_requests: list[Any] = []

    def CreateRecTask(self, request: Any) -> Any:  # noqa: N802
        self.create_requests.append(request)
        if self.create_error is not None:
            raise self.create_error
        return SimpleNamespace(Data=SimpleNamespace(TaskId=12345))

    def DescribeTaskStatus(self, request: Any) -> Any:  # noqa: N802
        self.describe_requests.append(request)
        return SimpleNamespace(Data=self.statuses.pop(0))


@pytest.fixture
def sample_audio(tmp_path: Path) -> Path:
    audio_path = tmp_path / "audio.mp3"
    audio_path.write_bytes(b"fake audio")
    return audio_path


def _provider(
    client: FakeAsrClient,
    cos_storage: FakeCosStorage,
    *,
    timeout_seconds: float = 0.05,
) -> TencentCloudProvider:
    return TencentCloudProvider(
        secret_id="sid",
        secret_key="skey",
        region="ap-beijing",
        poll_interval_seconds=0,
        timeout_seconds=timeout_seconds,
        cos_storage=cos_storage,  # type: ignore[arg-type]
        client=client,
    )


@pytest.mark.asyncio
async def test_transcribe_uploads_to_cos_and_submits_url_task(
    sample_audio: Path,
) -> None:
    cos_storage = FakeCosStorage()
    client = FakeAsrClient(
        [
            SimpleNamespace(
                Status=2,
                ResultDetail=[
                    SimpleNamespace(
                        FinalSentence="Hello world.",
                        StartMs=100,
                        EndMs=900,
                        SpeakerId=-1,
                    )
                ],
                Result="",
                AudioDuration=0.8,
            )
        ]
    )
    provider = _provider(client, cos_storage)

    result = await provider.transcribe(sample_audio)

    assert result.provider_name == "tencent_cloud"
    assert result.full_text == "Hello world."
    assert result.cost_usd == 0.0
    assert cos_storage.uploaded_paths == [sample_audio]
    assert cos_storage.deleted_keys == ["podlator/asr-audio/test/audio.mp3"]

    request = client.create_requests[0]
    assert request.SourceType == 0
    assert request.Url == "https://cos.example.com/audio.mp3"
    assert request.EngineModelType == "16k_zh_large"
    assert request.ResTextFormat == 2
    assert request.SpeakerDiarization == 0


@pytest.mark.asyncio
async def test_transcribe_polls_until_success(sample_audio: Path) -> None:
    cos_storage = FakeCosStorage()
    client = FakeAsrClient(
        [
            SimpleNamespace(Status=0, Result="", ResultDetail=[], AudioDuration=0),
            SimpleNamespace(Status=1, Result="", ResultDetail=[], AudioDuration=0),
            SimpleNamespace(
                Status=2,
                ResultDetail=[],
                Result="[0:0.020,0:2.380] fallback text",
                AudioDuration=2.38,
            ),
        ]
    )
    provider = _provider(client, cos_storage)

    result = await provider.transcribe(sample_audio)

    assert len(client.describe_requests) == 3
    assert [request.TaskId for request in client.describe_requests] == [
        12345,
        12345,
        12345,
    ]
    assert result.segments[0]["text"] == "fallback text"
    assert result.segments[0]["start"] == 0.02


@pytest.mark.asyncio
async def test_transcribe_raises_retryable_on_rate_limit(sample_audio: Path) -> None:
    cos_storage = FakeCosStorage()
    error = TencentCloudSDKException(
        "RequestLimitExceeded", "too many requests", "req-id"
    )
    client = FakeAsrClient([], create_error=error)
    provider = _provider(client, cos_storage, timeout_seconds=0.0)

    with pytest.raises(ProviderError) as exc_info:
        await provider.transcribe(sample_audio)

    assert exc_info.value.retryable is True
    assert cos_storage.deleted_keys == ["podlator/asr-audio/test/audio.mp3"]


@pytest.mark.asyncio
async def test_transcribe_raises_non_retryable_on_failed_task(
    sample_audio: Path,
) -> None:
    cos_storage = FakeCosStorage()
    client = FakeAsrClient(
        [
            SimpleNamespace(
                Status=3,
                ErrorMsg="audio url cannot be downloaded",
                Result="",
                ResultDetail=[],
                AudioDuration=0,
            )
        ]
    )
    provider = _provider(client, cos_storage, timeout_seconds=0.0)

    with pytest.raises(ProviderError) as exc_info:
        await provider.transcribe(sample_audio)

    assert exc_info.value.retryable is False
    assert "audio url cannot be downloaded" in str(exc_info.value)


@pytest.mark.asyncio
async def test_transcribe_times_out(sample_audio: Path) -> None:
    cos_storage = FakeCosStorage()
    client = FakeAsrClient(
        [
            SimpleNamespace(Status=1, Result="", ResultDetail=[], AudioDuration=0)
            for _ in range(100)
        ]
    )
    provider = _provider(client, cos_storage, timeout_seconds=0.0)

    with pytest.raises(ProviderError) as exc_info:
        await provider.transcribe(sample_audio)

    assert exc_info.value.retryable is True
    assert "timed out" in str(exc_info.value)


def test_parse_result_detail_to_segments() -> None:
    task_status = SimpleNamespace(
        ResultDetail=[
            SimpleNamespace(
                FinalSentence="Speaker text.",
                StartMs=1000,
                EndMs=2500,
                SpeakerId=2,
            )
        ],
        Result="ignored",
    )

    segments = parse_task_status(task_status)

    assert segments == [
        {
            "text": "Speaker text.",
            "start": 1.0,
            "end": 2.5,
            "speaker": "SPEAKER_2",
            "confidence": None,
        }
    ]


def test_parse_result_fallback_when_detail_missing() -> None:
    task_status = SimpleNamespace(
        ResultDetail=[],
        Result="[0:00:00.500,0:00:02.000] first\n[0:02.000,0:03.250] second",
    )

    segments = parse_task_status(task_status)

    assert [segment["text"] for segment in segments] == ["first", "second"]
    assert segments[0]["start"] == 0.5
    assert segments[1]["start"] == 2.0
