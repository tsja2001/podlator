"""日志模块测试。"""

from __future__ import annotations

from pathlib import Path

from podlator.logging import get_logger, setup_logging


def test_get_logger_returns_logger() -> None:
    """get_logger 返回可用的 logger。"""
    log = get_logger("test")
    assert log is not None


def test_setup_logging_creates_log_dir(tmp_path: Path) -> None:
    """setup_logging 自动创建日志目录。"""
    log_dir = tmp_path / "logs"
    setup_logging(log_level="INFO", json_enabled=True, log_dir=log_dir)
    assert log_dir.exists()


def test_logger_info_output(capsys) -> None:
    """logger.info 能正常输出。"""
    setup_logging(log_level="INFO", json_enabled=False)
    log = get_logger("test.output")
    log.info("test_event", key="value")
    captured = capsys.readouterr()
    assert "test_event" in captured.err or "test_event" in captured.out
