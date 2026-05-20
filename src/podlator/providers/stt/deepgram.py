"""Deepgram STT Provider 实现 — 通过 REST API 调用。"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

from podlator.errors import ProviderError
from podlator.graph.state import TranscriptSegment
from podlator.logging import get_logger
from podlator.providers.stt.base import STTProvider, STTResult

logger = get_logger(__name__)

# Deepgram Nova-3 价格: $0.0043/分钟
DEEPGRAM_COST_PER_MINUTE = 0.0043
# 带说话人分离 +$0.0002/分钟
DEEPGRAM_DIARIZE_COST_PER_MINUTE = 0.0002

DEEPGRAM_API_URL = "https://api.deepgram.com/v1/listen"


class DeepgramProvider(STTProvider):
    """Deepgram 转写 Provider，使用 REST API。"""

    def __init__(self, api_key: str, model: str = "nova-3") -> None:
        self.api_key = api_key
        self.model = model

    async def transcribe(
        self,
        audio_path: Path,
        *,
        language: str = "en",
        diarize: bool = True,
    ) -> STTResult:
        """转写音频文件，返回带时间戳的片段。"""
        log = logger.bind(provider="deepgram", model=self.model)

        if not audio_path.exists():
            raise ProviderError(
                "deepgram", f"Audio file not found: {audio_path}", retryable=False
            )

        params: dict[str, str | int] = {
            "model": self.model,
            "language": language,
            "smart_format": "true",
            "diarize": "true" if diarize else "false",
            "utterances": "true",
            "punctuate": "true",
        }

        audio_bytes = audio_path.read_bytes()

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    DEEPGRAM_API_URL,
                    params=params,
                    content=audio_bytes,
                    headers={
                        "Authorization": f"Token {self.api_key}",
                        "Content-Type": "audio/mp3",
                    },
                )
            duration_ms = (time.monotonic() - start) * 1000
        except httpx.TimeoutException as e:
            log.error("deepgram_timeout", audio_path=str(audio_path))
            raise ProviderError("deepgram", "Request timeout", retryable=True) from e
        except Exception as e:
            log.error(
                "deepgram_request_failed",
                audio_path=str(audio_path),
                error_type=type(e).__name__,
                error_msg=str(e),
            )
            raise ProviderError("deepgram", str(e), retryable=True) from e

        if response.status_code != 200:
            retryable = response.status_code in (429, 500, 502, 503, 504)
            log.error(
                "deepgram_api_failed",
                status_code=response.status_code,
                error_msg=response.text[:500],
                retryable=retryable,
            )
            raise ProviderError(
                "deepgram",
                f"API returned {response.status_code}: {response.text[:200]}",
                retryable=retryable,
            )

        data = response.json()
        segments, has_diarization = _parse_deepgram_response(data)
        audio_duration = _calculate_audio_duration(audio_bytes)
        cost = _calculate_cost(audio_duration, diarize)

        full_text = " ".join(s["text"] for s in segments)

        log.info(
            "stt_completed",
            provider="deepgram",
            audio_duration_seconds=audio_duration,
            segments_count=len(segments),
            cost_usd=cost,
            duration_ms=duration_ms,
        )
        return STTResult(
            segments=segments,
            full_text=full_text,
            has_diarization=has_diarization,
            provider_name="deepgram",
            duration_ms=duration_ms,
            cost_usd=cost,
        )


def _parse_deepgram_response(
    data: dict[str, Any],
) -> tuple[list[TranscriptSegment], bool]:
    """解析 Deepgram JSON 响应为 TranscriptSegment 列表。"""
    segments: list[TranscriptSegment] = []
    has_diarization = False

    results = data.get("results", {})
    channels = results.get("channels", [])

    for channel in channels:
        alternatives = channel.get("alternatives", [])
        for alt in alternatives:
            words = alt.get("words", [])
            if not words:
                continue

            # 合并连续相同 speaker 的 words 为一个 segment
            current_text_parts: list[str] = []
            current_start = words[0].get("start", 0.0)
            current_end = words[0].get("end", 0.0)
            current_speaker: str | None = None
            current_conf_sum = 0.0
            current_conf_count = 0

            for w in words:
                speaker = w.get("speaker")
                if speaker is not None:
                    has_diarization = True
                speaker_label = f"SPEAKER_{speaker}" if speaker is not None else None

                if speaker_label != current_speaker and current_text_parts:
                    # 完成上一个 segment
                    segments.append(
                        {
                            "text": " ".join(current_text_parts),
                            "start": float(current_start),
                            "end": float(current_end),
                            "speaker": current_speaker,
                            "confidence": (
                                current_conf_sum / current_conf_count
                                if current_conf_count > 0
                                else None
                            ),
                        }
                    )
                    current_text_parts = []

                if not current_text_parts:
                    current_start = w.get("start", 0.0)
                    current_speaker = speaker_label
                    current_conf_sum = 0.0
                    current_conf_count = 0

                current_text_parts.append(w.get("word", ""))
                current_end = w.get("end", 0.0)
                conf = w.get("confidence")
                if conf is not None:
                    current_conf_sum += conf
                    current_conf_count += 1

            # 最后一个 segment
            if current_text_parts:
                segments.append(
                    {
                        "text": " ".join(current_text_parts),
                        "start": float(current_start),
                        "end": float(current_end),
                        "speaker": current_speaker,
                        "confidence": (
                            current_conf_sum / current_conf_count
                            if current_conf_count > 0
                            else None
                        ),
                    }
                )

    return segments, has_diarization


def _calculate_audio_duration(audio_bytes: bytes) -> float:
    """估算音频时长（秒）。MP3 大致: 比特率 128kbps → 16 KB/s。"""
    # 简化估算：假设 128kbps MP3
    size_kb = len(audio_bytes) / 1024
    return size_kb / 16.0


def _calculate_cost(duration_seconds: float, diarize: bool) -> float:
    """计算 Deepgram 转写费用。"""
    minutes = duration_seconds / 60.0
    cost = minutes * DEEPGRAM_COST_PER_MINUTE
    if diarize:
        cost += minutes * DEEPGRAM_DIARIZE_COST_PER_MINUTE
    return round(cost, 6)
