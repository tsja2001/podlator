"""STT 转写 Provider 接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from podlator.graph.state import TranscriptSegment


@dataclass
class STTResult:
    """转写结果。"""

    segments: list[TranscriptSegment]
    full_text: str
    has_diarization: bool
    provider_name: str
    duration_ms: float
    cost_usd: float


class STTProvider(ABC):
    """STT 转写 Provider 接口。"""

    @abstractmethod
    async def transcribe(
        self,
        audio_path: Path,
        *,
        language: str = "en",
        diarize: bool = True,
    ) -> STTResult:
        """转写音频文件，返回带时间戳的片段。"""
        ...
