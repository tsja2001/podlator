"""ClaudeProvider 单元测试。"""

from __future__ import annotations

import pytest
import structlog
from pytest_httpx import HTTPXMock

from podlator.errors import ProviderError
from podlator.providers.llm.claude import ClaudeProvider

CLAUDE_MOCK_RESPONSE = {
    "id": "chatcmpl-claude-test",
    "object": "chat.completion",
    "model": "claude-opus-4.7",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "播客是一种通过互联网分发的音频节目形式。",
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {
        "prompt_tokens": 50,
        "completion_tokens": 30,
        "total_tokens": 80,
    },
}

CLAUDE_MOCK_RESPONSE_TRUNCATED = {
    "id": "chatcmpl-claude-truncated",
    "object": "chat.completion",
    "model": "claude-opus-4.7",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "这是一段被截断的中文文本，因为 max_tokens 设置太小",
            },
            "finish_reason": "length",
        }
    ],
    "usage": {
        "prompt_tokens": 500,
        "completion_tokens": 4096,
        "total_tokens": 4596,
    },
}


@pytest.fixture
def provider() -> ClaudeProvider:
    return ClaudeProvider(
        api_key="test-key",
        base_url="https://api.b.ai/v1",
        model="claude-opus-4.7",
        max_tokens=4096,
    )


@pytest.mark.asyncio
async def test_complete_success(
    provider: ClaudeProvider,
    httpx_mock: HTTPXMock,
) -> None:
    """正常调用返回 LLMResult。"""
    httpx_mock.add_response(
        url="https://api.b.ai/v1/chat/completions",
        method="POST",
        json=CLAUDE_MOCK_RESPONSE,
        status_code=200,
    )

    result = await provider.complete("用一句话描述什么是播客。")

    assert result.content
    assert result.model == "claude-opus-4.7"
    assert result.provider_name == "claude"
    assert result.tokens_in == 50
    assert result.tokens_out == 30
    assert result.cost_usd > 0


@pytest.mark.asyncio
async def test_complete_rate_limit(
    provider: ClaudeProvider,
    httpx_mock: HTTPXMock,
) -> None:
    """Rate limit 抛出 ProviderError(retryable=True)。"""
    httpx_mock.add_response(
        url="https://api.b.ai/v1/chat/completions",
        method="POST",
        status_code=429,
        json={"error": "Rate limit"},
        is_reusable=True,
    )

    with pytest.raises(ProviderError) as exc_info:
        await provider.complete("test")

    assert exc_info.value.retryable is True


@pytest.mark.asyncio
async def test_complete_auth_error(
    provider: ClaudeProvider,
    httpx_mock: HTTPXMock,
) -> None:
    """Auth error 抛出 ProviderError(retryable=False)。"""
    httpx_mock.add_response(
        url="https://api.b.ai/v1/chat/completions",
        method="POST",
        status_code=401,
        json={"error": "Unauthorized"},
    )

    with pytest.raises(ProviderError) as exc_info:
        await provider.complete("test")

    assert exc_info.value.retryable is False


@pytest.mark.asyncio
async def test_complete_surfaces_finish_reason_length(
    provider: ClaudeProvider,
    httpx_mock: HTTPXMock,
) -> None:
    """截断返回的 finish_reason 应为 length 且有告警。"""
    httpx_mock.add_response(
        url="https://api.b.ai/v1/chat/completions",
        method="POST",
        json=CLAUDE_MOCK_RESPONSE_TRUNCATED,
        status_code=200,
    )

    cap = structlog.testing.capture_logs()
    with cap as captured:
        result = await provider.complete("test")

    assert result.finish_reason == "length"

    truncation_events = [
        e for e in captured if e.get("event") == "llm_output_truncated"
    ]
    assert len(truncation_events) == 1
    assert truncation_events[0]["finish_reason"] == "length"
