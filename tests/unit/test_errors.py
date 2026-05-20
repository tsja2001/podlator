"""异常类测试。"""

from __future__ import annotations

import pytest

from podlator.errors import ConfigError, NodeError, PodlatorError, ProviderError


def test_node_error_attrs() -> None:
    """NodeError 属性正确。"""
    e = NodeError("test_node", "something went wrong", retryable=True)
    assert e.node_name == "test_node"
    assert e.retryable is True
    assert "[test_node] something went wrong" in str(e)


def test_provider_error_attrs() -> None:
    """ProviderError 属性正确。"""
    e = ProviderError("deepgram", "timeout", retryable=True)
    assert e.provider == "deepgram"
    assert e.retryable is True


def test_node_error_default_not_retryable() -> None:
    """NodeError 默认不可重试。"""
    e = NodeError("n", "msg")
    assert e.retryable is False


def test_config_error() -> None:
    """ConfigError 是 PodlatorError 子类。"""
    e = ConfigError("missing key")
    assert isinstance(e, PodlatorError)


def test_node_error_raises() -> None:
    """NodeError 可以正常 raise/catch。"""
    with pytest.raises(NodeError, match=r"\[n\] msg"):
        raise NodeError("n", "msg")
