"""LLM Provider 接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResult:
    """LLM 调用结果。"""

    content: str
    model: str
    provider_name: str
    tokens_in: int
    tokens_out: int
    duration_ms: float
    cost_usd: float


class LLMProvider(ABC):
    """LLM Provider 接口。"""

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 8192,
    ) -> LLMResult:
        """发送 prompt，返回补全结果。"""
        ...
