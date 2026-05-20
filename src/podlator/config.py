"""应用配置。从 .env 文件加载，环境变量覆盖。"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # ── API Keys ──
    deepgram_api_key: str = ""
    deepseek_api_key: str = ""
    claude_api_key: str = ""

    # ── Provider 选择 ──
    stt_provider: str = "deepgram"
    llm_provider_summarize: str = "deepseek"
    llm_provider_polish: str = "claude"

    # ── 路径 ──
    data_dir: Path = Field(default=Path("data"))
    audio_dir: Path = Field(default=Path("data/audio"))
    briefs_dir: Path = Field(default=Path("data/briefs"))
    log_dir: Path = Field(default=Path("data/logs"))

    # ── 日志 ──
    log_level: str = "INFO"
    log_json_enabled: bool = True

    # ── 数据库 ──
    database_path: str = "data/podlator.db"
    checkpoint_db_path: str = "data/checkpoints.sqlite"

    # ── API 服务 ──
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ── DeepSeek（OpenAI 兼容 API）──
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_max_tokens: int = 8192

    # ── Claude（第三方平台，OpenAI 兼容 API）──
    claude_base_url: str = "https://api.b.ai/v1"
    claude_model: str = "claude-opus-4.7"
    claude_max_tokens: int = 4096

    # ── Deepgram ──
    deepgram_model: str = "nova-3"
    deepgram_language: str = "en"
