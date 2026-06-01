"""Step: Draft Markdown → Polished Markdown。

通过 LLM 润色 Markdown 草稿，输出更流畅、更符合阅读习惯的中文简报。
"""

from __future__ import annotations

from podlator.config import Settings
from podlator.logging import get_logger
from podlator.prompts import load_prompt
from podlator.providers.llm import get_llm_provider

logger = get_logger(__name__)


async def polish_markdown(
    markdown: str,
    *,
    title: str | None = None,
    provider_name: str = "claude",
    settings: Settings | None = None,
) -> str:
    """润色 Markdown 草稿。

    行为：
    - 调用 LLM 对草稿进行润色。
    - 不改变核心信息，只优化表达、结构和可读性。

    Args:
        markdown: 输入 Markdown 草稿。
        title: 节目标题（可选，用于 prompt 上下文）。
        provider_name: LLM provider 名称。
        settings: 应用配置。

    Returns:
        润色后的 Markdown 字符串。
    """
    if settings is None:
        settings = Settings()

    provider = get_llm_provider(provider_name, settings)

    system_prompt, user_template = load_prompt("polish_final")

    display_title = title or "Podcast Episode"
    prompt = user_template.format(
        title=display_title,
        duration_seconds=0,
        chapters_content=markdown,
        date="",
    )

    result = await provider.complete(
        prompt, system=system_prompt, temperature=0.5, max_tokens=4096
    )
    return result.content.strip()
