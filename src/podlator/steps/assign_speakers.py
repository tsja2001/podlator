# ruff: noqa: E501  (long prompt strings)
"""Step: Transcript JSON → Transcript JSON with inferred speakers。

通过 LLM 推断说话人标签，只修改 speaker 字段，不修改正文和时间戳。
"""

from __future__ import annotations

import json

from podlator.config import Settings
from podlator.logging import get_logger
from podlator.providers.llm import get_llm_provider
from podlator.steps.models import TranscriptDocument, TranscriptSegmentModel

logger = get_logger(__name__)

_SPEAKER_SYSTEM_PROMPT = """You are a speaker diarization assistant. Your ONLY job is to assign speaker labels to transcript segments.

Rules:
1. You can ONLY assign speaker labels — you CANNOT modify segment text, timestamps, or indices.
2. You CANNOT translate, summarize, or polish any text.
3. Use context and conversational cues to infer who is speaking.
4. For segments where you cannot determine the speaker, use "UNKNOWN".
5. Try to be consistent: if you think the same person is speaking across multiple segments, use the same label (e.g., "SPEAKER_A", "SPEAKER_B").
6. Use descriptive labels if you can infer roles (e.g., "HOST", "GUEST", "INTERVIEWER").

Output a JSON array of objects with "index" and "speaker" fields ONLY. No additional text."""

_SPEAKER_USER_TEMPLATE = """Here are transcript segments. For each segment, assign the most likely speaker label based on context.

Segments:
{segments_text}

Output ONLY a JSON array:
[{{"index": 0, "speaker": "HOST"}}, {{"index": 1, "speaker": "GUEST"}}, ...]"""


def _format_segment_for_prompt(
    seg: TranscriptSegmentModel, include_timestamps: bool = True
) -> str:
    """将单个 segment 格式化为 prompt 行。"""
    if include_timestamps:
        return (
            f"[{seg.start:.2f} - {seg.end:.2f}] "
            f"index={seg.index} speaker={seg.speaker or 'None'}: "
            f"{seg.text}"
        )
    return f"index={seg.index} speaker={seg.speaker or 'None'}: {seg.text}"


async def assign_speakers(
    transcript: TranscriptDocument,
    *,
    provider_name: str = "deepseek",
    settings: Settings | None = None,
) -> TranscriptDocument:
    """通过 LLM 推断并分配说话人标签。

    行为：
    - 只修改 segments[*].speaker 字段。
    - 不改写 segments[*].text、start/end。
    - 不做章节切分、翻译、摘要或润色。

    Args:
        transcript: 输入 TranscriptDocument。
        provider_name: LLM provider 名称。
        settings: 应用配置（如为 None 则使用默认 Settings()）。

    Returns:
        更新了 speaker 字段的新 TranscriptDocument。

    Raises:
        ValueError: LLM 返回缺少必要字段。
    """
    if not transcript.segments:
        return transcript

    if settings is None:
        settings = Settings()

    provider = get_llm_provider(provider_name, settings)

    # 构造 prompt：每个 segment 一行，带上 index、时间戳和文本
    segments_lines = [_format_segment_for_prompt(seg) for seg in transcript.segments]
    segments_text = "\n".join(segments_lines)

    prompt = _SPEAKER_USER_TEMPLATE.format(segments_text=segments_text)

    result = await provider.complete(
        prompt,
        system=_SPEAKER_SYSTEM_PROMPT,
        temperature=0.2,
        max_tokens=4096,
    )

    # 解析 LLM 返回的 JSON
    content = result.content.strip()
    # LLM 可能会包裹在 ```json ``` 中
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        assignments = json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning(
            "assign_speakers_parse_failed",
            content_preview=content[:200],
            error=str(e),
        )
        return transcript

    if not isinstance(assignments, list):
        logger.warning(
            "assign_speakers_unexpected_format",
            content_preview=content[:200],
        )
        return transcript

    # 构建 index -> speaker 映射
    speaker_map: dict[int, str] = {}
    for item in assignments:
        if isinstance(item, dict) and "index" in item and "speaker" in item:
            speaker_map[item["index"]] = item["speaker"]

    # 更新 segments 的 speaker 字段
    updated_segments = []
    for seg in transcript.segments:
        new_speaker = speaker_map.get(seg.index, seg.speaker)
        updated_segments.append(seg.model_copy(update={"speaker": new_speaker}))

    return transcript.model_copy(update={"segments": updated_segments})
