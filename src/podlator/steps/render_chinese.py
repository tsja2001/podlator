# ruff: noqa: E501  (long prompt strings)
"""Step: Transcript + Chapters → Markdown。

支持两种模式：
- summary: 按章节生成中文精简摘要（复用 summarize_chapter prompt 语义）
- full: 按章节生成中文全文翻译（新增 translate_chapter_full prompt）
"""

from __future__ import annotations

import asyncio
from typing import Literal

from podlator.config import Settings
from podlator.logging import get_logger
from podlator.prompts import load_prompt
from podlator.providers.llm import get_llm_provider
from podlator.providers.llm.base import LLMProvider
from podlator.steps.models import ChapterDocument, ChapterModel, TranscriptDocument

logger = get_logger(__name__)

_FULL_SYSTEM_PROMPT = """You are a professional bilingual translator specializing in English-to-Chinese podcast translation.

Your task: translate the given English podcast chapter into fluent, natural Chinese.

Requirements:
1. Translate the FULL content — do not summarize or compress.
2. Use natural, spoken-style Chinese appropriate for podcast content.
3. Preserve the original meaning, tone, and nuance.
4. Keep speaker labels if present in the source.
5. Output ONLY the translated Chinese text. No explanations, no notes, no JSON."""

_FULL_USER_TEMPLATE = """Translate this podcast chapter into Chinese.

Chapter: {chapter_title} ({start:.0f}s - {end:.0f}s)

Original English transcript:
{chapter_text}

Full Chinese translation:"""


async def _render_single_chapter(
    provider: LLMProvider,
    mode: Literal["summary", "full"],
    chapter: ChapterModel,
    chapter_text: str,
    duration: float,
) -> tuple[int, str]:
    """渲染单个章节（summary 或 full），返回 (chapter_index, rendered_text)。"""
    if mode == "summary":
        system_prompt, user_template = load_prompt("summarize_chapter")
        prompt = user_template.format(
            chapter_title=chapter.title,
            start=chapter.start,
            end=chapter.end,
            chapter_text=chapter_text,
        )
        result = await provider.complete(
            prompt, system=system_prompt, temperature=0.3, max_tokens=4096
        )
        return chapter.index, result.content.strip()
    else:
        prompt = _FULL_USER_TEMPLATE.format(
            chapter_title=chapter.title,
            start=chapter.start,
            end=chapter.end,
            chapter_text=chapter_text,
        )
        result = await provider.complete(
            prompt,
            system=_FULL_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=8192,
        )
        return chapter.index, result.content.strip()


def _get_chapter_text(transcript: TranscriptDocument, chapter: ChapterModel) -> str:
    """从 transcript 中提取某个章节对应的文本。"""
    indices = set(chapter.segment_indices)
    if indices:
        texts = [seg.text for seg in transcript.segments if seg.index in indices]
        return " ".join(texts)
    # fallback: 按时间范围提取
    texts = [
        seg.text
        for seg in transcript.segments
        if chapter.start <= seg.start < chapter.end
    ]
    if texts:
        return " ".join(texts)
    return transcript.text


def _build_markdown(
    transcript: TranscriptDocument,
    chapters: ChapterDocument,
    rendered: dict[int, str],
    mode: Literal["summary", "full"],
) -> str:
    """将渲染后的章节组装成 Markdown 文档。"""
    title = transcript.source.title or "Untitled"
    lines = [f"# {title}", ""]

    if mode == "summary":
        lines.append("> 中文精简摘要")
    else:
        lines.append("> 中文全文翻译")

    lines.append("")

    for ch in sorted(chapters.chapters, key=lambda c: c.index):
        ch_title = ch.title
        lines.append(f"## {ch_title}")
        lines.append("")
        if ch.index in rendered:
            lines.append(rendered[ch.index])
        else:
            lines.append("*(章节渲染失败)*")
        lines.append("")

    return "\n".join(lines)


async def render_chinese(
    transcript: TranscriptDocument,
    chapters: ChapterDocument,
    *,
    mode: Literal["summary", "full"] = "summary",
    provider_name: str = "deepseek",
    settings: Settings | None = None,
    max_concurrency: int = 5,
) -> str:
    """按章节渲染输出 Markdown。

    Args:
        transcript: 输入 TranscriptDocument。
        chapters: 输入 ChapterDocument。
        mode: "summary"（精简摘要）或 "full"（全文翻译）。
        provider_name: LLM provider 名称。
        settings: 应用配置。
        max_concurrency: 最大并发章节数。

    Returns:
        渲染后的 Markdown 字符串。

    Raises:
        ValueError: chapters 为空。
    """
    if not chapters.chapters:
        raise ValueError("Chapters 为空，无法渲染")

    if settings is None:
        settings = Settings()

    provider = get_llm_provider(provider_name, settings)

    duration = (
        transcript.source.duration_seconds or transcript.segments[-1].end
        if transcript.segments
        else 0.0
    )

    semaphore = asyncio.Semaphore(max_concurrency)

    async def _render_with_limit(
        chapter: ChapterModel,
    ) -> tuple[int, str]:
        chapter_text = _get_chapter_text(transcript, chapter)
        async with semaphore:
            try:
                return await _render_single_chapter(
                    provider, mode, chapter, chapter_text, duration
                )
            except Exception as e:
                logger.warning(
                    "render_chapter_failed",
                    chapter_index=chapter.index,
                    chapter_title=chapter.title,
                    error=str(e),
                )
                return chapter.index, f"*(章节渲染失败: {e})*"

    tasks = [_render_with_limit(ch) for ch in chapters.chapters]
    results = await asyncio.gather(*tasks)

    rendered_map: dict[int, str] = {}
    for idx, text in results:
        rendered_map[idx] = text

    return _build_markdown(transcript, chapters, rendered_map, mode)
