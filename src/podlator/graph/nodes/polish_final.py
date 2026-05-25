"""节点：全局润色 + 引言/结论。使用 Claude Opus 4.7。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from podlator.config import Settings
from podlator.errors import ProviderError
from podlator.graph.nodes._base import node, node_logger
from podlator.graph.state import PodlatorState
from podlator.prompts import load_prompt
from podlator.providers.llm import get_llm_provider
from podlator.providers.llm.base import LLMResult

POLISH_FALLBACK_PROVIDER = "deepseek"


@node("polish_final")
async def run(state: PodlatorState) -> dict[str, Any]:
    log = node_logger(state, "polish_final")

    title = state.get("title", "Untitled")
    duration = state.get("duration_seconds", 0)
    chapters = state.get("chapters", [])
    if not chapters:
        log.warning("no_chapters_to_polish")
        return {"brief_markdown": ""}

    # 拼接章节内容
    chapters_content = ""
    for ch in chapters:
        chapters_content += f"### {ch['title']}\n\n{ch.get('summary_zh', '')}\n\n"

    settings = Settings()
    system, user_template = load_prompt("polish_final")

    user = user_template.format(
        title=title,
        duration_seconds=duration,
        chapters_content=chapters_content,
    )

    result = await _complete_with_fallback(
        settings=settings,
        prompt=user,
        system=system,
        log=log,
    )
    log.info(
        "polish_completed",
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_usd=result.cost_usd,
        provider=result.provider_name,
    )

    # 替换模板占位符为实际值
    duration_str = f"{duration / 60:.0f} 分钟" if duration > 0 else "未知"
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    brief = result.content.replace("{duration}", duration_str).replace(
        "{date}", date_str
    )

    return {"brief_markdown": brief, "total_cost_usd": result.cost_usd}


async def _complete_with_fallback(
    *,
    settings: Settings,
    prompt: str,
    system: str,
    log: Any,
) -> LLMResult:
    """优先使用配置的润色模型；网络/限流类错误时降级到 DeepSeek。

    这里的降级只覆盖可重试的 ProviderError，避免把 API key 错误、权限错误等
    配置问题静默吞掉。类似 JS 里的 catch 里只处理特定错误类型，其余继续 throw。
    """
    primary_provider_name = settings.llm_provider_polish
    provider = get_llm_provider(primary_provider_name, settings)
    try:
        return await provider.complete(prompt=prompt, system=system)
    except ProviderError as error:
        if not error.retryable or primary_provider_name == POLISH_FALLBACK_PROVIDER:
            raise

        log.warning(
            "polish_fallback_triggered",
            from_provider=primary_provider_name,
            to_provider=POLISH_FALLBACK_PROVIDER,
            error_msg=str(error),
            retryable=error.retryable,
        )
        fallback_provider = get_llm_provider(POLISH_FALLBACK_PROVIDER, settings)
        return await fallback_provider.complete(prompt=prompt, system=system)
