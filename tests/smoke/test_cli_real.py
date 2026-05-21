"""Smoke 测试：通过 CLI 执行真实 pipeline。

仅当 PODLATOR_RUN_SMOKE=1 时执行。
"""

from __future__ import annotations

import os
import subprocess

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("PODLATOR_RUN_SMOKE"),
    reason="Smoke tests disabled (set PODLATOR_RUN_SMOKE=1 to enable)",
)

SHORT_VIDEO_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"


def test_cli_run_real(tmp_path) -> None:
    """通过 CLI 执行真实 pipeline。"""
    result = subprocess.run(
        [
            "uv",
            "run",
            "podlator",
            "run",
            SHORT_VIDEO_URL,
        ],
        capture_output=True,
        text=True,
        timeout=120,
        env={
            **os.environ,
            "DATA_DIR": str(tmp_path),
            "DATABASE_PATH": str(tmp_path / "test.db"),
        },
    )
    assert result.returncode == 0, f"CLI 失败:\n{result.stderr}"
    assert "✅ 处理完成" in result.stdout
    assert "简报:" in result.stdout
