"""Step: Transcript → 抖音解说稿 Markdown。

通过 LLM 将播客访谈改写成抖音风格的中文解说稿。
与 render/polish（简报风格）不同，本 step 产出的是口语化、有观点、
按主题重组的解说稿，适合口播。
"""

from __future__ import annotations

from podlator.config import Settings
from podlator.logging import get_logger
from podlator.prompts import load_prompt
from podlator.providers.llm import get_llm_provider
from podlator.steps.models import TranscriptDocument, TranscriptSegmentModel

logger = get_logger(__name__)

# 默认值
DEFAULT_TARGET_WORDS = 3000
DEFAULT_MAX_INPUT_CHARS = 30000
DEFAULT_PROVIDER = "claude"


def _format_transcript_for_douyin(
    segments: list[TranscriptSegmentModel],
    max_chars: int = DEFAULT_MAX_INPUT_CHARS,
) -> str:
    """将 transcript segments 格式化为适合解说稿 prompt 的文本。

    - 合并相邻同说话人的文本（减少碎片化）
    - 按时间顺序排列（LLM 会自行重组）
    - 超过 max_chars 时智能截断（在段落边界截断）

    Args:
        segments: 转录片段列表。
        max_chars: 最大字符数（截断阈值）。

    Returns:
        格式化后的文本。
    """
    lines: list[str] = []
    char_count = 0

    for seg in segments:
        speaker = seg.speaker or "unknown"
        timestamp = f"[{int(seg.start // 60):02d}:{int(seg.start % 60):02d}]"
        line = f"{timestamp} {speaker}: {seg.text}"

        if char_count + len(line) > max_chars:
            # 到达截断点
            remaining = len(segments) - seg.index - 1
            if remaining > 0:
                lines.append(f"\n... (后续还有 {remaining} 条片段，已截断) ...\n")
            break

        lines.append(line)
        char_count += len(line) + 1  # +1 for newline

    return "\n".join(lines)


def _extract_speakers(segments: list[TranscriptSegmentModel]) -> str:
    """从 segments 中提取说话人列表。"""
    speakers: list[str] = []
    seen: set[str] = set()
    for seg in segments:
        if seg.speaker and seg.speaker not in seen:
            speakers.append(seg.speaker)
            seen.add(seg.speaker)
    if not speakers:
        return "未知"
    return "、".join(speakers)


def _estimate_duration_minutes(segments: list[TranscriptSegmentModel]) -> float:
    """估算音频时长（分钟）。"""
    if not segments:
        return 0.0
    return segments[-1].end / 60.0


async def generate_douyin_script(
    transcript: TranscriptDocument,
    *,
    title: str | None = None,
    provider_name: str = DEFAULT_PROVIDER,
    settings: Settings | None = None,
    target_words: int = DEFAULT_TARGET_WORDS,
    max_input_chars: int = DEFAULT_MAX_INPUT_CHARS,
) -> str:
    """将播客转录生成抖音风格中文解说稿。

    行为：
    - 加载 douyin_script prompt 模板。
    - 格式化 transcript 内容（含说话人标注）。
    - 调用 LLM 生成解说稿。
    - 不修改原 transcript 内容。

    Args:
        transcript: 输入 TranscriptDocument（建议已标注说话人）。
        title: 节目标题（默认使用 transcript.source.title）。
        provider_name: LLM provider 名称（默认 claude，质量更高）。
        settings: 应用配置。
        target_words: 目标字数（默认 3000）。
        max_input_chars: 输入内容最大字符数（防止 prompt 过长）。

    Returns:
        抖音解说稿 Markdown 字符串。

    Raises:
        ValueError: transcript.segments 为空。
        RuntimeError: LLM 调用失败。
    """
    if not transcript.segments:
        raise ValueError("Transcript segments 为空，无法生成解说稿")

    if settings is None:
        settings = Settings()

    provider = get_llm_provider(provider_name, settings)

    # 准备 prompt 变量
    display_title = title or transcript.source.title or "Untitled Podcast"
    duration_minutes = _estimate_duration_minutes(transcript.segments)
    speakers = _extract_speakers(transcript.segments)
    content = _format_transcript_for_douyin(transcript.segments, max_input_chars)

    logger.info(
        "douyin_script_generating",
        title=display_title,
        duration_minutes=round(duration_minutes, 1),
        speakers=speakers,
        content_chars=len(content),
        target_words=target_words,
        provider=provider_name,
    )

    # 加载 prompt 模板
    system_prompt, user_template = load_prompt("douyin_script")
    prompt = user_template.format(
        title=display_title,
        duration_minutes=duration_minutes,
        speakers=speakers,
        content=content,
        target_words=target_words,
    )

    try:
        result = await provider.complete(
            prompt,
            system=system_prompt,
            temperature=0.7,  # 解说稿需要一定创造性
            max_tokens=8192,
        )
    except Exception as e:
        logger.error(
            "douyin_script_llm_failed",
            provider=provider_name,
            error_type=type(e).__name__,
            error_msg=str(e),
            exc_info=True,
        )
        raise

    logger.info(
        "douyin_script_generated",
        output_chars=len(result.content),
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms,
    )

    return result.content.strip()
