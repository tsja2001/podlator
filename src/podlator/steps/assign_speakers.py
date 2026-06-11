# ruff: noqa: E501  (long prompt strings)
"""Step: Transcript JSON → Transcript JSON with inferred speakers。

通过 LLM 推断说话人标签，只修改 speaker 字段，不修改正文和时间戳。
支持分片处理长 transcript（shard + overlap + normalize）。
"""

from __future__ import annotations

import json
import re

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

# 默认分片参数
DEFAULT_SHARD_SIZE = 50  # 从 80 降到 50：每片输出更短，天然不易触顶
DEFAULT_SHARD_OVERLAP = 10

# 每个分片 LLM 调用的 max_tokens 上限（50 条 JSON 标注绰绰有余）
_SPEAKER_SHARD_MAX_TOKENS = 8192

# 正则：匹配一个完整的 {"index": N, "speaker": "X"} 对象（容忍空白）
_SPEAKER_OBJ_RE = re.compile(
    r'\{\s*"index"\s*:\s*(\d+)\s*,\s*"speaker"\s*:\s*"([^"]*)"\s*\}'
)


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


def _parse_llm_content(content: str) -> dict[int, str] | None:
    """解析 LLM 返回的 JSON，返回 {index: speaker} 映射。

    JSON 截断时（finish_reason=length），用正则抢救所有完整对象，不再整片丢弃。

    Returns:
        解析成功返回 dict，失败返回 None。
    """
    # LLM 可能会包裹在 ```json ``` 中
    clean = content.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        clean = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        assignments = json.loads(clean)
    except json.JSONDecodeError:
        # 截断抢救：正则提取所有完整对象，能救多少救多少
        salvaged = {int(idx): spk for idx, spk in _SPEAKER_OBJ_RE.findall(clean)}
        if salvaged:
            logger.warning(
                "assign_speakers_salvaged_partial_json",
                recovered=len(salvaged),
                content_preview=content[:200],
            )
            return salvaged
        logger.warning(
            "assign_speakers_parse_failed",
            content_preview=content[:200],
        )
        return None

    if not isinstance(assignments, list):
        logger.warning(
            "assign_speakers_unexpected_format",
            content_preview=content[:200],
        )
        return None

    speaker_map: dict[int, str] = {}
    for item in assignments:
        if isinstance(item, dict) and "index" in item and "speaker" in item:
            speaker_map[item["index"]] = item["speaker"]
    return speaker_map


def _shard_segments(
    segments: list[TranscriptSegmentModel],
    shard_size: int,
    shard_overlap: int,
) -> list[list[TranscriptSegmentModel]]:
    """将 segments 按 shard_size 分片，片间有 overlap 个 segment 的重叠。

    Args:
        segments: 完整 segment 列表。
        shard_size: 每个分片的 segment 数量。
        shard_overlap: 相邻分片重叠的 segment 数量。

    Returns:
        分片列表，每个分片是一个 segment 子列表。
    """
    if len(segments) <= shard_size:
        return [list(segments)]

    shards: list[list[TranscriptSegmentModel]] = []
    start = 0
    while start < len(segments):
        end = min(start + shard_size, len(segments))
        shards.append(list(segments[start:end]))
        if end >= len(segments):
            break
        start = end - shard_overlap
    return shards


async def _process_shard(
    shard: list[TranscriptSegmentModel],
    provider_name: str,
    settings: Settings,
) -> dict[int, str]:
    """处理单个分片：调 LLM 推断说话人，返回 {index: speaker} 映射。

    失败时返回空 dict。
    """
    try:
        provider = get_llm_provider(provider_name, settings)
    except Exception as e:
        logger.error("get_llm_provider_failed", provider=provider_name, error=str(e))
        return {}

    segments_lines = [_format_segment_for_prompt(seg) for seg in shard]
    segments_text = "\n".join(segments_lines)
    prompt = _SPEAKER_USER_TEMPLATE.format(segments_text=segments_text)

    try:
        result = await provider.complete(
            prompt,
            system=_SPEAKER_SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=_SPEAKER_SHARD_MAX_TOKENS,
        )
    except Exception as e:
        logger.error(
            "assign_speakers_shard_llm_failed",
            shard_size=len(shard),
            error=str(e),
            exc_info=True,
        )
        return {}

    if result.finish_reason == "length":
        logger.warning(
            "assign_speakers_shard_truncated",
            shard_size=len(shard),
            max_tokens=_SPEAKER_SHARD_MAX_TOKENS,
        )

    speaker_map = _parse_llm_content(result.content)
    if speaker_map is None:
        logger.warning(
            "assign_speakers_shard_parse_failed",
            shard_size=len(shard),
            content_preview=result.content[:200],
        )
        return {}

    logger.info(
        "assign_speakers_shard_completed",
        shard_size=len(shard),
        speakers_assigned=len(speaker_map),
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms,
    )
    return speaker_map


def _normalize_labels_across_shards(
    shard_results: list[dict[int, str]],
    shard_overlap: int,
) -> list[dict[int, str]]:
    """跨分片归一化说话人标签。

    使用重叠区域的 segment 建立跨分片标签映射：
    - 如果 shard N 的 segment X 标为 "HOST"，shard N+1 的同一 segment 标为 "SPEAKER_A"，
      则将 shard N+1 中所有 "SPEAKER_A" 替换为 "HOST"。

    Args:
        shard_results: 每个分片的 {index: speaker} 映射列表。
        shard_overlap: 分片重叠 segment 数量。

    Returns:
        归一化后的 shard_results 列表（原地修改 + 返回）。
    """
    for i in range(1, len(shard_results)):
        prev = shard_results[i - 1]
        curr = shard_results[i]

        # 在重叠区域找共同的 segment indices，建立映射
        label_map: dict[str, str] = {}
        for idx, curr_label in curr.items():
            if idx in prev:
                prev_label = prev[idx]
                if curr_label != prev_label and curr_label not in label_map:
                    label_map[curr_label] = prev_label

        if not label_map:
            continue

        # 应用映射到当前分片
        normalized: dict[int, str] = {}
        for idx, label in curr.items():
            normalized[idx] = label_map.get(label, label)
        shard_results[i] = normalized

        logger.debug(
            "shard_label_normalization",
            shard_index=i,
            label_mappings={k: v for k, v in label_map.items()},
        )

    return shard_results


def _merge_shard_results(
    segments: list[TranscriptSegmentModel],
    shard_results: list[dict[int, str]],
) -> dict[int, str]:
    """合并所有分片结果为一个完整的 {index: speaker} 映射。

    冲突处理：重叠区域优先使用前一个分片的结果。
    """
    merged: dict[int, str] = {}
    for shard_map in shard_results:
        for idx, label in shard_map.items():
            if idx not in merged:
                merged[idx] = label
    return merged


async def assign_speakers(
    transcript: TranscriptDocument,
    *,
    provider_name: str = "deepseek",
    settings: Settings | None = None,
    shard_size: int = DEFAULT_SHARD_SIZE,
    shard_overlap: int = DEFAULT_SHARD_OVERLAP,
) -> TranscriptDocument:
    """通过 LLM 推断并分配说话人标签。

    行为：
    - 只修改 segments[*].speaker 字段。
    - 不改写 segments[*].text、start/end。
    - 不做章节切分、翻译、摘要或润色。
    - 长 transcript 自动分片处理，保证分片边界说话人标签连续性。

    Args:
        transcript: 输入 TranscriptDocument。
        provider_name: LLM provider 名称。
        settings: 应用配置（如为 None 则使用默认 Settings()）。
        shard_size: 每个分片的 segment 数量（默认 80）。
        shard_overlap: 相邻分片重叠的 segment 数量（默认 10）。

    Returns:
        更新了 speaker 字段的新 TranscriptDocument。

    Raises:
        ValueError: LLM 返回缺少必要字段。
    """
    if not transcript.segments:
        return transcript

    if settings is None:
        settings = Settings()

    # 判断是否需要分片
    if len(transcript.segments) <= shard_size:
        # ── 不分片：使用原有逻辑 ──
        provider = get_llm_provider(provider_name, settings)

        segments_lines = [
            _format_segment_for_prompt(seg) for seg in transcript.segments
        ]
        segments_text = "\n".join(segments_lines)
        prompt = _SPEAKER_USER_TEMPLATE.format(segments_text=segments_text)

        result = await provider.complete(
            prompt,
            system=_SPEAKER_SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=_SPEAKER_SHARD_MAX_TOKENS,
        )

        speaker_map = _parse_llm_content(result.content)
        if speaker_map is None:
            return transcript

        # 构建 index -> speaker 映射
        # speaker_map 已在上面的 _parse_llm_content 中构建
    else:
        # ── 分片处理 ──
        logger.info(
            "assign_speakers_sharding",
            total_segments=len(transcript.segments),
            shard_size=shard_size,
            shard_overlap=shard_overlap,
        )

        shards = _shard_segments(transcript.segments, shard_size, shard_overlap)
        logger.info(
            "assign_speakers_shards_created",
            num_shards=len(shards),
            shard_sizes=[len(s) for s in shards],
        )

        # 并发处理所有分片
        import asyncio

        tasks = [_process_shard(shard, provider_name, settings) for shard in shards]
        shard_results = await asyncio.gather(*tasks)

        # 跨分片归一化标签
        shard_results = _normalize_labels_across_shards(
            list(shard_results), shard_overlap
        )

        # 合并
        speaker_map = _merge_shard_results(transcript.segments, shard_results)

    # 更新 segments 的 speaker 字段
    updated_segments = []
    for seg in transcript.segments:
        new_speaker = speaker_map.get(seg.index, seg.speaker)
        updated_segments.append(seg.model_copy(update={"speaker": new_speaker}))

    return transcript.model_copy(update={"segments": updated_segments})
