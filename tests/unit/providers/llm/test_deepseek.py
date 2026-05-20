"""DeepSeekProvider 单元测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from podlator.errors import ProviderError
from podlator.providers.llm.deepseek import DeepSeekProvider


@pytest.fixture
def provider() -> DeepSeekProvider:
    return DeepSeekProvider(
        api_key="test-key",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-flash",
        max_tokens=8192,
    )


@pytest.fixture
def mock_response() -> dict:
    fixture_path = (
        Path(__file__).parent.parent.parent.parent
        / "fixtures"
        / "responses"
        / "deepseek_response.json"
    )
    return json.loads(fixture_path.read_text())


@pytest.mark.asyncio
async def test_complete_success(
    provider: DeepSeekProvider,
    mock_response: dict,
    httpx_mock: HTTPXMock,
) -> None:
    """正常调用返回 LLMResult。"""
    httpx_mock.add_response(
        url="https://api.deepseek.com/chat/completions",
        method="POST",
        json=mock_response,
        status_code=200,
    )

    result = await provider.complete("你好，请介绍一下自己。")

    assert result.content
    assert result.model == "deepseek-v4-flash"
    assert result.provider_name == "deepseek"
    assert result.tokens_in == 100
    assert result.tokens_out == 50
    assert result.cost_usd > 0
    assert result.duration_ms > 0


@pytest.mark.asyncio
async def test_complete_with_system_prompt(
    provider: DeepSeekProvider,
    mock_response: dict,
    httpx_mock: HTTPXMock,
) -> None:
    """带 system prompt 的调用。"""
    httpx_mock.add_response(
        url="https://api.deepseek.com/chat/completions",
        method="POST",
        json=mock_response,
        status_code=200,
    )

    result = await provider.complete("用户 prompt", system="你是一个有用的助手。")
    assert result.content


@pytest.mark.asyncio
async def test_complete_rate_limit(
    provider: DeepSeekProvider,
    httpx_mock: HTTPXMock,
) -> None:
    """429 错误抛出 ProviderError(retryable=True)。"""
    # OpenAI SDK 会重试，所以设置 is_reusable
    httpx_mock.add_response(
        url="https://api.deepseek.com/chat/completions",
        method="POST",
        status_code=429,
        json={"error": "Rate limit exceeded"},
        is_reusable=True,
    )

    with pytest.raises(ProviderError) as exc_info:
        await provider.complete("test")

    assert exc_info.value.retryable is True


@pytest.mark.asyncio
async def test_complete_auth_error(
    provider: DeepSeekProvider,
    httpx_mock: HTTPXMock,
) -> None:
    """401 错误抛出 ProviderError(retryable=False)。"""
    httpx_mock.add_response(
        url="https://api.deepseek.com/chat/completions",
        method="POST",
        status_code=401,
        json={"error": "Unauthorized"},
    )

    with pytest.raises(ProviderError) as exc_info:
        await provider.complete("test")

    assert exc_info.value.retryable is False


@pytest.mark.asyncio
async def test_complete_server_error(
    provider: DeepSeekProvider,
    httpx_mock: HTTPXMock,
) -> None:
    """500 错误抛出 ProviderError(retryable=True)。"""
    httpx_mock.add_response(
        url="https://api.deepseek.com/chat/completions",
        method="POST",
        status_code=500,
        json={"error": "Internal server error"},
        is_reusable=True,
    )

    with pytest.raises(ProviderError) as exc_info:
        await provider.complete("test")

    assert exc_info.value.retryable is True
