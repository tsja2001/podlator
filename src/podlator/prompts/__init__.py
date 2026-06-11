"""Prompt 模板加载工具。"""

from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str) -> tuple[str, str]:
    """加载 prompt 模板，返回 (system_prompt, user_prompt_template)。

    模板文件用 '# System Prompt' 和 '# User Prompt' 分隔。
    """
    path = PROMPTS_DIR / f"{name}.md"
    content = path.read_text(encoding="utf-8")

    parts = content.split("# User Prompt")
    system = parts[0].replace("# System Prompt", "").strip()
    user_template = parts[1].strip() if len(parts) > 1 else ""

    return system, user_template


def load_rubric(version: str = "v3") -> str:
    """加载评分标准全文（用于注入 judge prompt）。

    Raises:
        FileNotFoundError: 指定版本的 rubric 文件不存在。
    """
    path = PROMPTS_DIR / f"rubric_{version}.md"
    if not path.exists():
        available = sorted(p.stem for p in PROMPTS_DIR.glob("rubric_*.md"))
        raise FileNotFoundError(f"Rubric {version!r} 不存在。可用版本: {available}")
    return path.read_text(encoding="utf-8")
