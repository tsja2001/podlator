"""文件路径管理。"""

from __future__ import annotations

from pathlib import Path


def get_audio_dir(data_dir: Path, task_id: str) -> Path:
    """返回任务的音频目录，自动创建。"""
    p = data_dir / "audio" / task_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_brief_dir(data_dir: Path, task_id: str) -> Path:
    """返回任务的简报目录，自动创建。"""
    p = data_dir / "briefs" / task_id
    p.mkdir(parents=True, exist_ok=True)
    return p
