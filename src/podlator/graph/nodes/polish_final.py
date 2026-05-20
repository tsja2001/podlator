"""节点：全局润色 + 引言/结论。使用 Claude Opus 4.7。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from podlator.config import Settings
from podlator.graph.nodes._base import node, node_logger
from podlator.graph.state import PodlatorState
from podlator.prompts import load_prompt
from podlator.providers.llm import get_llm_provider


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
    provider = get_llm_provider(settings.llm_provider_polish, settings)
    system, user_template = load_prompt("polish_final")

    user = user_template.format(
        title=title,
        duration_seconds=duration,
        chapters_content=chapters_content,
    )

    result = await provider.complete(prompt=user, system=system)
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

    return {"brief_markdown": brief}
