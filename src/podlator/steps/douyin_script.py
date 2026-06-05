"""Step: Transcript → 抖音解说稿 Markdown。

通过 LLM 将播客访谈改写成抖音风格的中文解说稿。

v3：两段式生成
- Stage1：便宜模型（DeepSeek）出「解说蓝图」
- Stage2：强 CLI 模型（claude -p / codex exec）据蓝图扩写定稿到 6000 字
- 可选字数补足回路（最多 2 轮）
- --simple 保留单段式作为降级
"""

from __future__ import annotations

from typing import Any

from podlator.config import Settings
from podlator.errors import ProviderError
from podlator.logging import get_logger
from podlator.prompts import load_prompt
from podlator.providers.llm import get_llm_provider
from podlator.providers.llm.base import LLMResult
from podlator.steps.models import TranscriptDocument, TranscriptSegmentModel

logger = get_logger(__name__)

# 默认值
DEFAULT_TARGET_WORDS = 6000
DEFAULT_MAX_INPUT_CHARS = 36000
DEFAULT_PROVIDER = "claude"
# Stage2 字数不足时的降级 provider
FALLBACK_PROVIDER = "deepseek"
# 字数补足回路最大轮数
MAX_SUPPLEMENT_ROUNDS = 2


# ------------------------------------------------------------------
# 文本格式化（复用原有逻辑）
# ------------------------------------------------------------------


def _format_transcript_for_douyin(
    segments: list[TranscriptSegmentModel],
    max_chars: int = DEFAULT_MAX_INPUT_CHARS,
) -> str:
    """将 transcript segments 格式化为适合解说稿 prompt 的文本。

    - 合并相邻同说话人的文本（减少碎片化）
    - 按时间顺序排列（LLM 会自行重组）
    - 超过 max_chars 时智能截断（在段落边界截断）
    """
    lines: list[str] = []
    char_count = 0

    for seg in segments:
        speaker = seg.speaker or "unknown"
        timestamp = f"[{int(seg.start // 60):02d}:{int(seg.start % 60):02d}]"
        line = f"{timestamp} {speaker}: {seg.text}"

        if char_count + len(line) > max_chars:
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


def _count_chinese_chars(text: str) -> int:
    """统计文本中中文字符数（含中文标点）。"""
    count = 0
    for ch in text:
        if "一" <= ch <= "鿿" or "　" <= ch <= "〿" or "＀" <= ch <= "￯":
            count += 1
        elif ch in "，。！？；：''（）【】《》—…·":
            count += 1
    # 如果中文很少，回退到 len()
    return count if count > 50 else len(text)


# ------------------------------------------------------------------
# 主入口
# ------------------------------------------------------------------


async def generate_douyin_script(
    transcript: TranscriptDocument,
    *,
    title: str | None = None,
    provider_name: str = DEFAULT_PROVIDER,
    settings: Settings | None = None,
    target_words: int = DEFAULT_TARGET_WORDS,
    max_input_chars: int = DEFAULT_MAX_INPUT_CHARS,
    simple: bool = False,
    blueprint_provider: str | None = None,
    finalize_provider: str | None = None,
) -> str:
    """将播客转录生成抖音风格中文解说稿（v3：两段式）。

    默认流程：
    1. Stage1：便宜模型出「解说蓝图」
    2. Stage2：强 CLI 模型据蓝图扩写定稿
    3. 字数不足时触发补足回路（最多 2 轮）

    Args:
        transcript: 输入 TranscriptDocument（建议已标注说话人）。
        title: 节目标题（默认使用 transcript.source.title）。
        provider_name: 单段式（simple）模式的 provider（默认 claude）。
        settings: 应用配置。
        target_words: 目标字数（默认 6000）。
        max_input_chars: 输入内容最大字符数。
        simple: 使用原始单段式生成（不拆 blueprint + finalize）。
        blueprint_provider: Stage1 blueprint provider（默认 config.summarize）。
        finalize_provider: Stage2 定稿 provider（默认 config.polish）。

    Returns:
        抖音解说稿 Markdown 字符串。

    Raises:
        ValueError: transcript.segments 为空。
        RuntimeError: LLM 调用失败且无法降级。
    """
    if not transcript.segments:
        raise ValueError("Transcript segments 为空，无法生成解说稿")

    if settings is None:
        settings = Settings()

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
        mode="simple" if simple else "two_stage",
    )

    if simple:
        return await _generate_simple(
            content=content,
            display_title=display_title,
            duration_minutes=duration_minutes,
            speakers=speakers,
            target_words=target_words,
            provider_name=(finalize_provider or blueprint_provider or provider_name),
            settings=settings,
        )

    # ── 两段式 ──
    bp_provider = blueprint_provider or settings.llm_provider_summarize
    fz_provider = finalize_provider or settings.llm_provider_polish

    # Stage 1: 生成解说蓝图
    logger.info(
        "douyin_blueprint_starting",
        provider=bp_provider,
        target_words=target_words,
    )
    blueprint = await _generate_blueprint(
        content=content,
        title=display_title,
        duration_minutes=duration_minutes,
        speakers=speakers,
        target_words=target_words,
        provider_name=bp_provider,
        settings=settings,
    )
    logger.info(
        "douyin_blueprint_completed",
        blueprint_chars=len(blueprint),
        provider=bp_provider,
    )

    # Stage 2: 据蓝图定稿
    min_words = int(target_words * 0.9)
    logger.info(
        "douyin_finalize_starting",
        provider=fz_provider,
        target_words=target_words,
        min_words=min_words,
    )
    draft = await _finalize_from_blueprint(
        content=content,
        blueprint=blueprint,
        title=display_title,
        speakers=speakers,
        target_words=target_words,
        min_words=min_words,
        provider_name=fz_provider,
        settings=settings,
    )
    current_words = _count_chinese_chars(draft)
    logger.info(
        "douyin_finalize_completed",
        words=current_words,
        target_words=target_words,
        provider=fz_provider,
    )

    # Stage 2.5: 字数补足回路
    if current_words < min_words:
        draft = await _supplement_words_loop(
            draft=draft,
            current_words=current_words,
            target_words=target_words,
            min_words=min_words,
            blueprint=blueprint,
            provider_name=fz_provider,
            settings=settings,
        )

    final_words = _count_chinese_chars(draft)
    logger.info(
        "douyin_script_generated",
        final_words=final_words,
        target_words=target_words,
        mode="two_stage",
    )

    return draft.strip()


# ------------------------------------------------------------------
# 单段式（simple 模式，保留原有行为）
# ------------------------------------------------------------------


async def _generate_simple(
    *,
    content: str,
    display_title: str,
    duration_minutes: float,
    speakers: str,
    target_words: int,
    provider_name: str,
    settings: Settings,
) -> str:
    """原始单段式生成：一次 LLM 调用完成。"""
    provider = get_llm_provider(provider_name, settings)

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
            temperature=0.7,
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
        "douyin_script_generated_simple",
        output_chars=len(result.content),
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms,
    )

    return result.content.strip()


# ------------------------------------------------------------------
# Stage 1: 解说蓝图
# ------------------------------------------------------------------


async def _generate_blueprint(
    *,
    content: str,
    title: str,
    duration_minutes: float,
    speakers: str,
    target_words: int,
    provider_name: str,
    settings: Settings,
) -> str:
    """Stage1：用便宜模型生成解说蓝图。"""
    provider = get_llm_provider(provider_name, settings)

    system_prompt, user_template = load_prompt("douyin_blueprint")
    prompt = user_template.format(
        title=title,
        duration_minutes=duration_minutes,
        speakers=speakers,
        content=content,
        target_words=target_words,
    )

    import time

    start = time.monotonic()
    try:
        result = await provider.complete(
            prompt,
            system=system_prompt,
            temperature=0.3,  # 蓝图需要结构化输出，温度低一点
            max_tokens=4096,
        )
        duration_ms = (time.monotonic() - start) * 1000
    except Exception as e:
        duration_ms = (time.monotonic() - start) * 1000
        logger.error(
            "blueprint_generation_failed",
            provider=provider_name,
            error_type=type(e).__name__,
            error_msg=str(e),
            duration_ms=duration_ms,
            exc_info=True,
        )
        raise

    logger.info(
        "blueprint_generated",
        provider=provider_name,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_usd=result.cost_usd,
        duration_ms=duration_ms,
    )

    return result.content.strip()


# ------------------------------------------------------------------
# Stage 2: 据蓝图定稿
# ------------------------------------------------------------------


async def _finalize_from_blueprint(
    *,
    content: str,
    blueprint: str,
    title: str,
    speakers: str,
    target_words: int,
    min_words: int,
    provider_name: str,
    settings: Settings,
) -> str:
    """Stage2：用强 CLI 模型据蓝图扩写定稿。失败时降级到 API provider。"""
    system_prompt, user_template = load_prompt("douyin_finalize")
    prompt = user_template.format(
        title=title,
        speakers=speakers,
        target_words=target_words,
        min_words=min_words,
        blueprint=blueprint,
        content=content,
    )

    log = logger.bind(provider=provider_name, target_words=target_words)

    result = await _complete_with_fallback(
        settings=settings,
        prompt=prompt,
        system=system_prompt,
        primary_provider_name=provider_name,
        fallback_provider_name=FALLBACK_PROVIDER,
        log=log,
    )

    log.info(
        "finalize_completed",
        output_chars=len(result.content),
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms,
        actual_provider=result.provider_name,
    )

    return result.content.strip()


# ------------------------------------------------------------------
# 字数补足回路
# ------------------------------------------------------------------


async def _supplement_words_loop(
    *,
    draft: str,
    current_words: int,
    target_words: int,
    min_words: int,
    blueprint: str,
    provider_name: str,
    settings: Settings,
) -> str:
    """字数不足时续写补足，最多 MAX_SUPPLEMENT_ROUNDS 轮。"""
    log = logger.bind(
        current_words=current_words,
        target_words=target_words,
        min_words=min_words,
    )

    for round_num in range(1, MAX_SUPPLEMENT_ROUNDS + 1):
        log.info(
            "supplement_round_starting",
            round=round_num,
            current_words=current_words,
        )

        supplement_system = (
            "你是抖音科技解说稿写手。你的任务是在已有草稿基础上续写补充内容，"
            "不重复已有内容、不重写已有段落。只输出新增的段落，第一句用自然的口语过渡衔接。"
        )
        supplement_user = (
            f"下面是已写好的解说稿草稿，当前约 {current_words} 字，"
            f"距目标 {target_words} 字还差不少。\n"
            f"请在**不重复已有内容、不重写已有段落**的前提下，继续把篇幅补足到目标字数。\n\n"
            f"补充方式：挑蓝图里还没写透的主题 / 外部知识点继续深入，"
            f"可在合适处插入更多例子、背景、点评。\n"
            f"**只输出新增的段落**（会被接到草稿后面），"
            f"第一句用自然的口语过渡衔接，保持同样的风格。\n\n"
            f"## 解说蓝图\n{blueprint}\n\n"
            f"## 当前草稿\n{draft}"
        )

        result = await _complete_with_fallback(
            settings=settings,
            prompt=supplement_user,
            system=supplement_system,
            primary_provider_name=provider_name,
            fallback_provider_name=FALLBACK_PROVIDER,
            log=log,
        )

        supplement = result.content.strip()
        if supplement:
            # 追加到草稿后面
            draft = draft.rstrip() + "\n\n" + supplement
            current_words = _count_chinese_chars(draft)
            log.info(
                "supplement_round_completed",
                round=round_num,
                new_words=current_words,
                supplement_chars=len(supplement),
            )

        if current_words >= min_words:
            log.info(
                "supplement_target_reached",
                rounds=round_num,
                final_words=current_words,
            )
            break
    else:
        # 2 轮后仍不足
        log.warning(
            "supplement_insufficient",
            final_words=current_words,
            target_words=target_words,
            max_rounds=MAX_SUPPLEMENT_ROUNDS,
        )

    return draft


# ------------------------------------------------------------------
# 降级逻辑（参考 polish_final.py 的 _complete_with_fallback）
# ------------------------------------------------------------------


async def _complete_with_fallback(
    *,
    settings: Settings,
    prompt: str,
    system: str,
    primary_provider_name: str,
    fallback_provider_name: str,
    log: Any,
) -> LLMResult:
    """优先使用主 provider；网络/限流/CLI 不可用时降级到 fallback。

    只覆盖可重试的 ProviderError，认证/权限错误继续抛出。
    """
    provider = get_llm_provider(primary_provider_name, settings)
    try:
        return await provider.complete(prompt=prompt, system=system)
    except ProviderError as error:
        # 不可重试错误 → 直接抛
        if not error.retryable:
            raise
        # 如果主 provider 就是 fallback，不要再降级到自己
        if primary_provider_name == fallback_provider_name:
            raise

        log.warning(
            "finalize_fallback_triggered",
            from_provider=primary_provider_name,
            to_provider=fallback_provider_name,
            error_msg=str(error),
            retryable=error.retryable,
        )
        fallback = get_llm_provider(fallback_provider_name, settings)
        return await fallback.complete(prompt=prompt, system=system)
    except FileNotFoundError as e:
        # CLI 工具不存在
        if primary_provider_name == fallback_provider_name:
            raise ProviderError(
                primary_provider_name,
                f"CLI 工具未安装或不在 PATH 中: {e}",
                retryable=False,
            ) from e

        log.warning(
            "finalize_fallback_triggered",
            from_provider=primary_provider_name,
            to_provider=fallback_provider_name,
            reason="cli_not_found",
            error_msg=str(e),
        )
        fallback = get_llm_provider(fallback_provider_name, settings)
        return await fallback.complete(prompt=prompt, system=system)
