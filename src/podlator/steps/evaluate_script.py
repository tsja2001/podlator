"""Step: LLM judge 评分（结合程序 lint + LLM 语义评分）。

先跑 lint，再调 LLM judge，合并修订指令后返回。
"""

from __future__ import annotations

import json
import time

from podlator.config import Settings
from podlator.errors import ProviderError
from podlator.logging import get_logger
from podlator.prompts import load_prompt, load_rubric
from podlator.providers.llm import get_llm_provider
from podlator.steps.lint_script import lint_script
from podlator.steps.models import (
    DimensionScore,
    JudgeReport,
    LintStats,
)

logger = get_logger(__name__)

# Judge prompt 最多重试次数（含首次）
_MAX_JUDGE_ATTEMPTS = 2


def _parse_json_block(text: str) -> str:
    """剥离可能的 ```json 代码块包裹。"""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return text.strip()


def _build_judge_prompt(
    script: str,
    lint_stats: LintStats,
    rubric_version: str = "v3",
    reference_points: str | None = None,
) -> tuple[str, str]:
    """构建 judge 的 system + user prompt。"""
    system, user_template = load_prompt("judge_score")
    rubric = load_rubric(rubric_version)
    ref_text = reference_points if reference_points else "（无参照论点清单）"
    lint_text = json.dumps(
        {
            "char_count": lint_stats.char_count,
            "long_sentence_ratio": lint_stats.long_sentence_ratio,
            "short_sentence_ratio": lint_stats.short_sentence_ratio,
            "interaction_density": lint_stats.interaction_density,
            "truncation_suspected": lint_stats.truncation_suspected,
        },
        ensure_ascii=False,
    )

    user = user_template.format(
        rubric=rubric,
        reference_points=ref_text,
        lint_stats=lint_text,
        script=script,
    )
    return system, user


def _code_recompute_total(dimensions: list[DimensionScore]) -> float:
    """代码复核 total_score（处理 -1 折算）。"""
    total = 0.0
    max_of_skipped = 0.0
    for d in dimensions:
        if d.score >= 0:
            total += d.score
        else:
            # score == -1 表示该维度不计分
            max_of_skipped += d.max_score

    total_max = sum(d.max_score for d in dimensions)
    effective_max = total_max - max_of_skipped
    if effective_max > 0 and max_of_skipped > 0:
        total = total / effective_max * total_max
    return round(total, 1)


def _code_recompute_verdict(
    total_score: float, dimensions: list[DimensionScore]
) -> str:
    """代码复核 verdict：total >= 80 且无单维 < 60% 满分 → pass。"""
    if total_score < 80:
        return "needs_revision"
    for d in dimensions:
        if d.score >= 0 and d.max_score > 0:
            if d.score < d.max_score * 0.6:
                return "needs_revision"
    return "pass"


async def evaluate_script(
    script: str,
    *,
    settings: Settings | None = None,
    provider_name: str | None = None,
    rubric_version: str = "v3",
    reference_points: str | None = None,
    target_words: int | None = None,
) -> tuple[JudgeReport, LintStats]:
    """先跑 lint，再调 LLM judge，合并修订指令后返回。

    - lint 的硬伤指令 append 到 JudgeReport.revision_directives
    - reference_points 为 None 时，user prompt 中该槽位填「（无参照论点清单）」
    - LLM 返回非法 JSON：重试 1 次；再失败抛 ProviderError
    - JSON 合法但缺字段/类型不符：同样走重试-失败路径（用 pydantic 校验）
    - 解析时先剥离可能的 ```json 代码块包裹（模型常见违规，宽容处理）
    """
    if settings is None:
        settings = Settings()
    if provider_name is None:
        provider_name = settings.llm_provider_judge

    # Step 1: 程序 lint
    lint_stats, lint_issues = lint_script(script, target_words=target_words)

    # Step 2: LLM judge
    system, user_prompt = _build_judge_prompt(
        script,
        lint_stats,
        rubric_version=rubric_version,
        reference_points=reference_points,
    )

    provider = get_llm_provider(provider_name, settings)

    last_error: str | None = None
    for attempt in range(1, _MAX_JUDGE_ATTEMPTS + 1):
        start = time.monotonic()
        try:
            result = await provider.complete(
                user_prompt,
                system=system,
                temperature=0.1,  # 评分任务要低温
            )
            duration_ms = (time.monotonic() - start) * 1000

            logger.info(
                "judge_api_call_completed",
                provider=provider_name,
                model=result.model,
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                cost_usd=result.cost_usd,
                duration_ms=duration_ms,
                attempt=attempt,
            )
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            logger.error(
                "judge_api_call_failed",
                provider=provider_name,
                error_type=type(e).__name__,
                error_msg=str(e),
                attempt=attempt,
                duration_ms=duration_ms,
            )
            last_error = str(e)
            continue

        # 尝试解析 JSON
        try:
            cleaned = _parse_json_block(result.content)
            raw = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(
                "judge_json_parse_failed",
                attempt=attempt,
                error=str(e),
                content_preview=result.content[:200],
            )
            last_error = f"JSON parse error: {e}"
            if attempt < _MAX_JUDGE_ATTEMPTS:
                # 重试：追加提醒
                user_prompt = user_prompt.rstrip() + (
                    "\n上次输出不是合法 JSON，这次只输出 JSON 对象本身。"
                )
                continue
            raise ProviderError(
                provider_name,
                f"judge 输出无法解析（{_MAX_JUDGE_ATTEMPTS} 次尝试）: {last_error}",
                retryable=False,
            )

        # 用 pydantic 校验 JSON 结构
        try:
            report = JudgeReport(**raw)
        except Exception as e:
            logger.warning(
                "judge_pydantic_validation_failed",
                attempt=attempt,
                error=str(e),
            )
            last_error = f"Pydantic validation error: {e}"
            if attempt < _MAX_JUDGE_ATTEMPTS:
                user_prompt = user_prompt.rstrip() + (
                    "\n上次输出的 JSON 结构不符合要求"
                    f"（{e}），这次只输出符合结构的 JSON 对象本身。"
                )
                continue
            raise ProviderError(
                provider_name,
                f"judge 输出字段不符（{_MAX_JUDGE_ATTEMPTS} 次尝试）: {last_error}",
                retryable=False,
            )

        # 代码复核 verdict 和 total_score
        computed_total = _code_recompute_total(report.dimensions)
        if abs(computed_total - report.total_score) > 0.5:
            logger.warning(
                "judge_total_mismatch",
                llm_total=report.total_score,
                computed=computed_total,
            )
            report.total_score = computed_total

        computed_verdict = _code_recompute_verdict(
            report.total_score, report.dimensions
        )
        if computed_verdict != report.verdict:
            logger.warning(
                "judge_verdict_overridden",
                llm_verdict=report.verdict,
                computed=computed_verdict,
            )
            report.verdict = computed_verdict  # type: ignore[assignment]

        # 合并 lint 硬伤指令
        report.revision_directives = list(report.revision_directives) + lint_issues

        return report, lint_stats

    # 所有重试都失败
    raise ProviderError(
        provider_name,
        f"judge 调用失败（{_MAX_JUDGE_ATTEMPTS} 次尝试）: {last_error}",
        retryable=False,
    )
