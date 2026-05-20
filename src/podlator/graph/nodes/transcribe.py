"""节点：STT 转写音频为文本。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from podlator.config import Settings
from podlator.graph.nodes._base import node, node_logger
from podlator.graph.state import PodlatorState
from podlator.providers.stt import get_stt_provider


@node("transcribe")
async def run(state: PodlatorState) -> dict[str, Any]:
    log = node_logger(state, "transcribe")

    audio_path = state.get("audio_path", "")
    if not audio_path:
        log.error("missing_audio_path")
        return {}

    settings = Settings()
    provider = get_stt_provider(settings)

    result = await provider.transcribe(Path(audio_path))

    full_text = " ".join(s["text"] for s in result.segments)

    log.info(
        "transcription_completed",
        stt_provider=result.provider_name,
        segments_count=len(result.segments),
        has_diarization=result.has_diarization,
        cost_usd=result.cost_usd,
    )

    return {
        "transcript_segments": result.segments,
        "transcript_text": full_text,
        "stt_provider": result.provider_name,
        "has_diarization": result.has_diarization,
    }
