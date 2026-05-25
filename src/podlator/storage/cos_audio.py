"""腾讯 COS 音频暂存，负责上传、预签名和清理临时音频。"""

from __future__ import annotations

import asyncio
import mimetypes
from pathlib import Path
from uuid import uuid4

from qcloud_cos import CosConfig, CosS3Client  # type: ignore[import-untyped]

from podlator.logging import get_logger

logger = get_logger(__name__)


class TencentCosAudioStorage:
    """把本地音频临时放到 COS，并生成 ASR 可拉取的 GET 预签名 URL。"""

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        secret_id: str,
        secret_key: str,
        prefix: str = "podlator/asr-audio",
        token: str = "",
        scheme: str = "https",
        presigned_expires_seconds: int = 21600,
        delete_after_transcribe: bool = True,
        client: CosS3Client | None = None,
    ) -> None:
        self.bucket = bucket
        self.region = region
        self.prefix = prefix.strip("/")
        self.presigned_expires_seconds = presigned_expires_seconds
        self.delete_after_transcribe = delete_after_transcribe

        if client is not None:
            self._client = client
            return

        config = CosConfig(
            Region=region,
            SecretId=secret_id,
            SecretKey=secret_key,
            Token=token or None,
            Scheme=scheme,
        )
        self._client = CosS3Client(config)

    def build_object_key(self, audio_path: Path, *, task_id: str | None = None) -> str:
        """生成隔离的对象 key，避免不同任务同名音频互相覆盖。"""
        namespace = task_id or uuid4().hex
        filename = audio_path.name or "audio"
        if not self.prefix:
            return f"{namespace}/{filename}"
        return f"{self.prefix}/{namespace}/{filename}"

    async def upload_and_presign(
        self, audio_path: Path, *, task_id: str | None = None
    ) -> tuple[str, str]:
        """上传音频并返回 `(object_key, presigned_url)`。"""
        object_key = self.build_object_key(audio_path, task_id=task_id)
        content_type = (
            mimetypes.guess_type(audio_path.name)[0] or "application/octet-stream"
        )

        await asyncio.to_thread(
            self._client.upload_file,
            Bucket=self.bucket,
            Key=object_key,
            LocalFilePath=str(audio_path),
            ContentType=content_type,
        )
        presigned_url = await asyncio.to_thread(
            self._client.get_presigned_url,
            Bucket=self.bucket,
            Key=object_key,
            Method="GET",
            Expired=self.presigned_expires_seconds,
        )

        logger.info(
            "cos_audio_uploaded",
            provider="tencent_cos",
            bucket=self.bucket,
            key=object_key,
            path=str(audio_path),
            size_bytes=audio_path.stat().st_size,
        )
        return object_key, str(presigned_url)

    async def delete(self, object_key: str) -> None:
        """删除临时对象。删除失败不吞异常，由调用方决定是否继续。"""
        await asyncio.to_thread(
            self._client.delete_object,
            Bucket=self.bucket,
            Key=object_key,
        )
        logger.info(
            "cos_audio_deleted",
            provider="tencent_cos",
            bucket=self.bucket,
            key=object_key,
        )
