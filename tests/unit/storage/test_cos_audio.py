"""腾讯 COS 音频暂存单元测试。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from podlator.storage.cos_audio import TencentCosAudioStorage


class FakeCosClient:
    """记录 COS SDK 调用，避免单元测试访问真实网络。"""

    def __init__(self) -> None:
        self.uploads: list[dict[str, Any]] = []
        self.presigns: list[dict[str, Any]] = []
        self.deletes: list[dict[str, Any]] = []

    def upload_file(self, **kwargs: Any) -> None:
        self.uploads.append(kwargs)

    def get_presigned_url(self, **kwargs: Any) -> str:
        self.presigns.append(kwargs)
        return "https://cos.example.com/signed-audio"

    def delete_object(self, **kwargs: Any) -> None:
        self.deletes.append(kwargs)


@pytest.fixture
def sample_audio(tmp_path: Path) -> Path:
    audio_path = tmp_path / "audio.mp3"
    audio_path.write_bytes(b"fake audio")
    return audio_path


def test_build_object_key_uses_prefix_task_id_and_filename(sample_audio: Path) -> None:
    client = FakeCosClient()
    storage = TencentCosAudioStorage(
        bucket="bucket-123",
        region="ap-beijing",
        secret_id="sid",
        secret_key="skey",
        prefix="/podlator/asr-audio/",
        client=client,  # type: ignore[arg-type]
    )

    key = storage.build_object_key(sample_audio, task_id="task-001")

    assert key == "podlator/asr-audio/task-001/audio.mp3"


@pytest.mark.asyncio
async def test_upload_and_presign_calls_cos_sdk(sample_audio: Path) -> None:
    client = FakeCosClient()
    storage = TencentCosAudioStorage(
        bucket="bucket-123",
        region="ap-beijing",
        secret_id="sid",
        secret_key="skey",
        prefix="podlator/asr-audio",
        presigned_expires_seconds=600,
        client=client,  # type: ignore[arg-type]
    )

    key, url = await storage.upload_and_presign(sample_audio, task_id="task-001")

    assert key == "podlator/asr-audio/task-001/audio.mp3"
    assert url == "https://cos.example.com/signed-audio"
    assert client.uploads == [
        {
            "Bucket": "bucket-123",
            "Key": key,
            "LocalFilePath": str(sample_audio),
            "ContentType": "audio/mpeg",
        }
    ]
    assert client.presigns == [
        {
            "Bucket": "bucket-123",
            "Key": key,
            "Method": "GET",
            "Expired": 600,
        }
    ]


@pytest.mark.asyncio
async def test_delete_calls_cos_sdk() -> None:
    client = FakeCosClient()
    storage = TencentCosAudioStorage(
        bucket="bucket-123",
        region="ap-beijing",
        secret_id="sid",
        secret_key="skey",
        client=client,  # type: ignore[arg-type]
    )

    await storage.delete("podlator/asr-audio/task-001/audio.mp3")

    assert client.deletes == [
        {
            "Bucket": "bucket-123",
            "Key": "podlator/asr-audio/task-001/audio.mp3",
        }
    ]
