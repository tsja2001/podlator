"""腾讯云 ASR Provider，通过 COS URL 创建异步录音文件识别任务。"""

from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path
from typing import Any, Protocol, cast

from tencentcloud.asr.v20190614 import (  # type: ignore[import-untyped]
    asr_client,
    models,
)
from tencentcloud.common import credential  # type: ignore[import-untyped]
from tencentcloud.common.exception.tencent_cloud_sdk_exception import (  # type: ignore[import-untyped]
    TencentCloudSDKException,
)

from podlator.errors import ProviderError
from podlator.graph.state import TranscriptSegment
from podlator.logging import get_logger
from podlator.providers.stt.base import STTProvider, STTResult
from podlator.storage.cos_audio import TencentCosAudioStorage

logger = get_logger(__name__)

TENCENT_PROVIDER_NAME = "tencent_cloud"
PENDING_STATUSES = {0, 1}
SUCCESS_STATUS = 2
FAILED_STATUS = 3
RETRYABLE_ERROR_CODES = (
    "RequestLimitExceeded",
    "LimitExceeded",
    "InternalError",
    "ResourceUnavailable",
)
RESULT_LINE_PATTERN = re.compile(
    r"^\[(?P<start>[^,\]]+),(?P<end>[^\]]+)\]\s*(?P<text>.+)$"
)


class TencentAsrClient(Protocol):
    """腾讯 ASR SDK 客户端的最小协议，便于单元测试注入 fake。"""

    def CreateRecTask(self, request: models.CreateRecTaskRequest) -> Any: ...  # noqa: N802

    def DescribeTaskStatus(  # noqa: N802
        self, request: models.DescribeTaskStatusRequest
    ) -> Any: ...


class TencentCloudProvider(STTProvider):
    """腾讯云录音文件识别 Provider。"""

    def __init__(
        self,
        *,
        secret_id: str,
        secret_key: str,
        region: str = "ap-shanghai",
        engine_model_type: str = "16k_zh_large",
        res_text_format: int = 2,
        speaker_diarization: int = 0,
        poll_interval_seconds: float = 3.0,
        timeout_seconds: float = 10800.0,
        cos_storage: TencentCosAudioStorage,
        client: TencentAsrClient | None = None,
    ) -> None:
        self.region = region
        self.engine_model_type = engine_model_type
        self.res_text_format = res_text_format
        self.speaker_diarization = speaker_diarization
        self.poll_interval_seconds = poll_interval_seconds
        self.timeout_seconds = timeout_seconds
        self.cos_storage = cos_storage

        if client is not None:
            self._client = client
        else:
            cred = credential.Credential(secret_id, secret_key)
            self._client = asr_client.AsrClient(cred, region)

    async def transcribe(
        self,
        audio_path: Path,
        *,
        language: str = "en",
        diarize: bool = True,
    ) -> STTResult:
        """转写音频文件，返回带时间戳的片段。"""
        del language, diarize
        log = logger.bind(provider=TENCENT_PROVIDER_NAME, model=self.engine_model_type)

        if not audio_path.exists():
            raise ProviderError(
                TENCENT_PROVIDER_NAME,
                f"Audio file not found: {audio_path}",
                retryable=False,
            )

        start = time.monotonic()
        object_key: str | None = None
        try:
            object_key, audio_url = await self.cos_storage.upload_and_presign(
                audio_path
            )
            task_id = await self._create_task(
                audio_url=audio_url, audio_path=audio_path
            )
            task_status = await self._poll_until_finished(task_id)
        except TencentCloudSDKException as e:
            retryable = _is_retryable_sdk_error(e)
            log.error(
                "api_call_failed",
                provider=TENCENT_PROVIDER_NAME,
                endpoint="TencentCloudASR",
                error_type=type(e).__name__,
                error_msg=str(e),
                retryable=retryable,
                exc_info=True,
            )
            raise ProviderError(
                TENCENT_PROVIDER_NAME, str(e), retryable=retryable
            ) from e
        finally:
            if object_key and self.cos_storage.delete_after_transcribe:
                try:
                    await self.cos_storage.delete(object_key)
                except Exception as e:
                    log.warning(
                        "cos_audio_delete_failed",
                        provider="tencent_cos",
                        key=object_key,
                        error_type=type(e).__name__,
                        error_msg=str(e),
                    )

        duration_ms = (time.monotonic() - start) * 1000
        segments = parse_task_status(task_status)
        full_text = " ".join(segment["text"] for segment in segments)
        has_diarization = any(segment["speaker"] is not None for segment in segments)
        audio_duration = float(_get_value(task_status, "AudioDuration", 0.0) or 0.0)

        log.info(
            "stt_completed",
            provider=TENCENT_PROVIDER_NAME,
            model=self.engine_model_type,
            audio_duration_seconds=audio_duration,
            segments_count=len(segments),
            cost_usd=0.0,
            duration_ms=duration_ms,
        )
        return STTResult(
            segments=segments,
            full_text=full_text,
            has_diarization=has_diarization,
            provider_name=TENCENT_PROVIDER_NAME,
            duration_ms=duration_ms,
            cost_usd=0.0,
        )

    async def _create_task(self, *, audio_url: str, audio_path: Path) -> int:
        request = models.CreateRecTaskRequest()
        request.EngineModelType = self.engine_model_type
        request.ChannelNum = 1
        request.ResTextFormat = self.res_text_format
        request.SourceType = 0
        request.Url = audio_url
        request.SpeakerDiarization = self.speaker_diarization
        request.EmotionRecognition = 0
        request.EmotionalEnergy = 0
        request.FilterDirty = 0
        request.FilterPunc = 0
        request.FilterModal = 0
        request.ConvertNumMode = 1

        start = time.monotonic()
        response = await asyncio.to_thread(self._client.CreateRecTask, request)
        duration_ms = (time.monotonic() - start) * 1000
        task = _get_value(response, "Data", None)
        task_id = _get_value(task, "TaskId", None)
        if task_id is None:
            raise ProviderError(
                TENCENT_PROVIDER_NAME,
                "CreateRecTask response missing Data.TaskId",
                retryable=True,
            )

        logger.info(
            "api_call_completed",
            provider=TENCENT_PROVIDER_NAME,
            endpoint="CreateRecTask",
            status_code=200,
            duration_ms=duration_ms,
            audio_duration_seconds=0.0,
            cost_usd=0.0,
            audio_size_bytes=audio_path.stat().st_size,
        )
        return int(task_id)

    async def _poll_until_finished(self, task_id: int) -> Any:
        deadline = time.monotonic() + self.timeout_seconds
        attempts = 0

        while True:
            attempts += 1
            request = models.DescribeTaskStatusRequest()
            request.TaskId = task_id

            start = time.monotonic()
            response = await asyncio.to_thread(self._client.DescribeTaskStatus, request)
            duration_ms = (time.monotonic() - start) * 1000
            task_status = _get_value(response, "Data", None)
            status = int(_get_value(task_status, "Status", -1))

            logger.info(
                "api_call_completed",
                provider=TENCENT_PROVIDER_NAME,
                endpoint="DescribeTaskStatus",
                status_code=200,
                duration_ms=duration_ms,
                asr_task_id=task_id,
                asr_status=status,
                poll_attempts=attempts,
                cost_usd=0.0,
            )

            if status == SUCCESS_STATUS:
                return task_status
            if status == FAILED_STATUS:
                error_msg = str(
                    _get_value(task_status, "ErrorMsg", "") or "ASR task failed"
                )
                raise ProviderError(TENCENT_PROVIDER_NAME, error_msg, retryable=False)
            if status not in PENDING_STATUSES:
                raise ProviderError(
                    TENCENT_PROVIDER_NAME,
                    f"Unknown ASR task status: {status}",
                    retryable=True,
                )
            if time.monotonic() >= deadline:
                raise ProviderError(
                    TENCENT_PROVIDER_NAME,
                    f"ASR task timed out after {self.timeout_seconds} seconds",
                    retryable=True,
                )

            await asyncio.sleep(self.poll_interval_seconds)


def parse_task_status(task_status: Any) -> list[TranscriptSegment]:
    """从 DescribeTaskStatus.Data 解析项目内部 TranscriptSegment。"""
    result_detail = _get_value(task_status, "ResultDetail", None) or []
    segments = _parse_result_detail(cast(list[Any], result_detail))
    if segments:
        return segments

    result = str(_get_value(task_status, "Result", "") or "")
    segments = _parse_result_fallback(result)
    if segments:
        return segments

    logger.warning(
        "tencent_asr_result_empty",
        provider=TENCENT_PROVIDER_NAME,
        has_result=bool(result),
    )
    return [
        {
            "text": result,
            "start": 0.0,
            "end": 0.0,
            "speaker": None,
            "confidence": None,
        }
    ]


def _parse_result_detail(result_detail: list[Any]) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    for item in result_detail:
        text = str(
            _get_value(item, "FinalSentence", None)
            or _get_value(item, "WrittenText", None)
            or _get_value(item, "SliceSentence", None)
            or ""
        ).strip()
        if not text:
            continue

        start_ms = float(_get_value(item, "StartMs", 0) or 0)
        end_ms = float(_get_value(item, "EndMs", start_ms) or start_ms)
        speaker_id = _get_value(item, "SpeakerId", None)
        speaker = (
            f"SPEAKER_{speaker_id}"
            if speaker_id is not None and int(speaker_id) >= 0
            else None
        )
        segments.append(
            {
                "text": text,
                "start": start_ms / 1000.0,
                "end": end_ms / 1000.0,
                "speaker": speaker,
                "confidence": None,
            }
        )
    return segments


def _parse_result_fallback(result: str) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    plain_lines: list[str] = []

    for line in result.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        match = RESULT_LINE_PATTERN.match(stripped)
        if match is None:
            plain_lines.append(stripped)
            continue

        segments.append(
            {
                "text": match.group("text").strip(),
                "start": _parse_timestamp(match.group("start")),
                "end": _parse_timestamp(match.group("end")),
                "speaker": None,
                "confidence": None,
            }
        )

    if segments:
        return segments
    if plain_lines:
        logger.warning(
            "tencent_asr_result_without_timestamps",
            provider=TENCENT_PROVIDER_NAME,
        )
        return [
            {
                "text": " ".join(plain_lines),
                "start": 0.0,
                "end": 0.0,
                "speaker": None,
                "confidence": None,
            }
        ]
    return []


def _parse_timestamp(value: str) -> float:
    parts = value.split(":")
    try:
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
        return float(value)
    except ValueError:
        logger.warning(
            "tencent_asr_timestamp_parse_failed",
            provider=TENCENT_PROVIDER_NAME,
            timestamp=value,
        )
        return 0.0


def _get_value(obj: Any, name: str, default: Any) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _is_retryable_sdk_error(error: TencentCloudSDKException) -> bool:
    code = str(getattr(error, "code", "") or "")
    return any(code.startswith(prefix) for prefix in RETRYABLE_ERROR_CODES)
