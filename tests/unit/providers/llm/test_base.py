"""LLM Provider 基础类型单元测试。"""

from __future__ import annotations

from podlator.providers.llm.base import LLMResult


def test_llm_result_finish_reason_defaults_none() -> None:
    """不传 finish_reason 时默认应为 None（向后兼容）。"""
    result = LLMResult(
        content="hello",
        model="test-model",
        provider_name="test",
        tokens_in=10,
        tokens_out=5,
        duration_ms=100.0,
        cost_usd=0.001,
    )
    assert result.finish_reason is None
