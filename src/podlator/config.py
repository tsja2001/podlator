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

    # ── Tencent ASR ──
    tencent_app_id: str = ""
    tencent_secret_id: str = ""
    tencent_secret_key: str = ""
    tencent_asr_region: str = "ap-shanghai"
    tencent_asr_engine_model_type: str = "16k_zh_large"
    tencent_asr_res_text_format: int = 2
    tencent_asr_speaker_diarization: int = 0
    tencent_asr_poll_interval_seconds: float = 3.0
    tencent_asr_timeout_seconds: float = 10800.0

    # ── Tencent COS ──
    tencent_cos_bucket: str = ""
    tencent_cos_region: str = ""
    tencent_cos_secret_id: str = ""
    tencent_cos_secret_key: str = ""
    tencent_cos_token: str = ""
    tencent_cos_prefix: str = "podlator/asr-audio"
    tencent_cos_scheme: str = "https"
    tencent_cos_presigned_expires_seconds: int = 21600
    tencent_cos_delete_after_transcribe: bool = True

    # ── CLI Tool Provider（本机 CLI 唤起的强模型）──
    # backend: "claude" | "codex" — 用哪个 CLI 工具
    cli_tool_backend: str = "claude"
    # Claude CLI 模型（如 claude-sonnet-4-6 / claude-opus-4-8）
    cli_tool_claude_model: str = "claude-sonnet-4-6"
    # Codex CLI 模型（留空用默认 gpt-5.5；ChatGPT 账号不支持 gpt-5）
    cli_tool_codex_model: str = ""
    # 子进程超时（秒）
    cli_tool_timeout_s: int = 600

    # ── Speech Transcriber（外部 CLI 工具）──
    speech_transcriber_project_dir: str = (
        "/Users/mac/Project_Personal/speech-transcriber"
    )
    speech_transcriber_provider: str = "tencent_cloud"
