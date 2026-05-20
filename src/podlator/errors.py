"""异常类定义。"""

from __future__ import annotations


class PodlatorError(Exception):
    """基础异常。"""


class NodeError(PodlatorError):
    """节点执行失败。"""

    def __init__(
        self, node_name: str, message: str, *, retryable: bool = False
    ) -> None:
        self.node_name = node_name
        self.retryable = retryable
        super().__init__(f"[{node_name}] {message}")


class ProviderError(PodlatorError):
    """外部 Provider 调用失败。"""

    def __init__(self, provider: str, message: str, *, retryable: bool = False) -> None:
        self.provider = provider
        self.retryable = retryable
        super().__init__(f"[{provider}] {message}")


class ConfigError(PodlatorError):
    """配置错误。"""
