"""结构化日志配置。支持控制台彩色输出 + JSON 文件 + WebSocket 推送。"""

from __future__ import annotations

import logging
from datetime import UTC
from pathlib import Path
from typing import Any

import structlog
from structlog.typing import EventDict, WrappedLogger


def _add_timestamp(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """为每个日志事件追加 ISO 8601 时间戳。"""
    from datetime import datetime

    event_dict["timestamp"] = datetime.now(UTC).isoformat()
    return event_dict


def setup_logging(
    log_level: str = "INFO",
    json_enabled: bool = True,
    *,
    log_dir: Path | None = None,
) -> None:
    """初始化 structlog，同时输出到控制台和 JSON 文件。

    Args:
        log_level: 日志级别，DEBUG/INFO/WARNING/ERROR/CRITICAL。
        json_enabled: 是否同时写 JSON 文件。
        log_dir: 日志目录，默认 data/logs/。
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors: list[Any] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        _add_timestamp,
    ]

    renderers: list[Any] = []

    # 控制台输出：彩色 pretty
    renderers.append(structlog.dev.ConsoleRenderer(colors=True))

    # JSON 文件输出
    if json_enabled and log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "podlator.log"
        file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
        file_handler.setLevel(level)

        json_processor = structlog.processors.JSONRenderer()

        formatter = structlog.stdlib.ProcessorFormatter(
            processor=json_processor,
            foreign_pre_chain=shared_processors,
        )
        file_handler.setFormatter(formatter)

        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 设置根 logger 级别
    logging.getLogger().setLevel(level)

    # 控制台 handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=True),
        foreign_pre_chain=shared_processors,
    )
    console_handler.setFormatter(console_formatter)
    logging.getLogger().handlers = [
        h
        for h in logging.getLogger().handlers
        if not isinstance(h, logging.StreamHandler)
    ]
    logging.getLogger().addHandler(console_handler)


def get_logger(name: str) -> Any:
    """获取 structlog logger 实例。

    相当于 JS 的 `console` 替代，但输出结构化 JSON。
    """
    return structlog.get_logger(name)
