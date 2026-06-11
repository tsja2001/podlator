"""Claude LLM Provider 实现 — 第三方平台 OpenAI 兼容 API。"""

from __future__ import annotations

import time

from openai import AsyncOpenAI

from podlator.errors import ProviderError
from podlator.logging import get_logger
from podlator.providers.llm.base import LLMProvider, LLMResult

logger = get_logger(__name__)

# Claude Opus 4.7 第三方平台定价（每百万 token，参考 b.ai 平台）
CLAUDE_INPUT_PRICE = 15.0  # $/1M tokens
CLAUDE_OUTPUT_PRICE = 75.0  # $/1M tokens


class ClaudeProvider(LLMProvider):
    """Claude Opus 4.7，通过第三方 OpenAI 兼容 API 调用。"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        max_tokens: int = 4096,
    ) -> None:
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.default_max_tokens = max_tokens

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 0,
    ) -> LLMResult:
        """发送 prompt，返回补全结果。"""
        log = logger.bind(provider="claude", model=self.model)

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        start = time.monotonic()
        effective_max_tokens = max_tokens or self.default_max_tokens
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=effective_max_tokens,
            )
            duration_ms = (time.monotonic() - start) * 1000
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            retryable = "RateLimit" in type(e).__name__ or not _is_auth_error(e)
            log.error(
                "llm_call_failed",
                provider="claude",
                error_type=type(e).__name__,
                error_msg=str(e),
                retryable=retryable,
                duration_ms=duration_ms,
            )
            raise ProviderError("claude", str(e), retryable=retryable) from e

        usage = response.usage
        tokens_in = usage.prompt_tokens if usage else 0
        tokens_out = usage.completion_tokens if usage else 0
        content = response.choices[0].message.content or ""
        finish_reason = response.choices[0].finish_reason  # "stop" / "length" / ...
        cost = _calculate_cost(tokens_in, tokens_out)

        if finish_reason == "length":
            log.warning(
                "llm_output_truncated",
                provider="claude",
                model=self.model,
                finish_reason=finish_reason,
                max_tokens=effective_max_tokens,
                tokens_out=tokens_out,
                hint="增大 max_tokens，或减小输入/分片",
            )

        log.info(
            "llm_completed",
            provider="claude",
            model=self.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
            duration_ms=duration_ms,
            finish_reason=finish_reason,
        )
        return LLMResult(
            content=content,
            model=self.model,
            provider_name="claude",
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_ms=duration_ms,
            cost_usd=cost,
            finish_reason=finish_reason,
        )


def _calculate_cost(tokens_in: int, tokens_out: int) -> float:
    """计算 Claude 调用费用。"""
    cost = (tokens_in / 1_000_000) * CLAUDE_INPUT_PRICE
    cost += (tokens_out / 1_000_000) * CLAUDE_OUTPUT_PRICE
    return round(cost, 8)


def _is_auth_error(e: Exception) -> bool:
    """判断是否为认证错误（不可重试）。"""
    return "Authentication" in type(e).__name__ or "Permission" in type(e).__name__
