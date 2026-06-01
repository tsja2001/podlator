"""节点：STT 转写音频为文本。

通过 steps/transcribe.py 调用外部 speech-transcriber CLI。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from podlator.config import Settings
from podlator.graph.nodes._base import node, node_logger
from podlator.graph.state import PodlatorState
from podlator.steps.transcribe import transcribe_audio


@node("transcribe")
async def run(state: PodlatorState) -> dict[str, Any]:
    log = node_logger(state, "transcribe")

    audio_path = state.get("audio_path", "")
    if not audio_path:
        log.error("missing_audio_path")
        return {}

    settings = Settings()
    doc = await transcribe_audio(
        Path(audio_path),
        provider_name=settings.speech_transcriber_provider,
        speech_transcriber_project_dir=settings.speech_transcriber_project_dir,
    )

    log.info(
        "transcription_completed",
        stt_provider=doc.provider.name,
        segments_count=len(doc.segments),
        cost_usd=doc.provider.cost_usd,
    )

    # 映射 TranscriptDocument → PodlatorState
    segments = [
        {
            "text": seg.text,
            "start": seg.start,
            "end": seg.end,
            "speaker": seg.speaker,
            "confidence": seg.confidence,
        }
        for seg in doc.segments
    ]

    return {
        "transcript_segments": segments,
        "transcript_text": doc.text,
        "stt_provider": doc.provider.name,
        "has_diarization": any(s["speaker"] for s in segments),
        "total_cost_usd": doc.provider.cost_usd,
    }
