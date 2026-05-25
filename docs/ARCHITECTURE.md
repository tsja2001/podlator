# 架构规格

> 本文件是 AI 实现代码的**具体规格参考**。包含所有数据结构、接口、路由的精确定义。
> 遇到设计疑问时，以本文件为准。

---

## 1. 系统总览

```
┌────────────┐     ┌──────────────┐     ┌────────────────┐
│   CLI      │────→│   FastAPI    │────→│  LangGraph     │
│  (Typer)   │     │  + WebSocket │     │  State Machine │
└────────────┘     └──────┬───────┘     └───────┬────────┘
                          │                     │
                   ┌──────┴───────┐      ┌──────┴────────┐
                   │   SQLite     │      │   Providers   │
                   │   Storage    │      │ STT/LLM/DL    │
                   └──────────────┘      └───────────────┘
```

- **CLI** → 直接调用 LangGraph 执行 pipeline
- **FastAPI** → Web UI 的后端，管理任务队列，WebSocket 推送日志
- **LangGraph** → 状态机核心，编排 8 个节点
- **Providers** → 外部 API 的抽象层（可替换实现）
- **Storage** → SQLite 任务记录 + 本地文件管理

---

## 2. PodlatorState 完整定义

> 这是 LangGraph 状态机的核心数据结构。所有节点读写此 State。

```python
"""src/podlator/graph/state.py"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


def _merge_dicts(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """合并两个 dict，用于 LangGraph reducer。"""
    return {**a, **b}


class TranscriptSegment(TypedDict):
    """一条转写片段。"""

    text: str                    # 文本内容
    start: float                 # 开始时间（秒）
    end: float                   # 结束时间（秒）
    speaker: str | None          # 说话人标签，如 "SPEAKER_0"；无分离时为 None
    confidence: float | None     # 转写置信度 0.0-1.0；不支持时为 None


class Chapter(TypedDict):
    """一个章节。"""

    index: int                   # 章节序号，从 0 开始
    title: str                   # 章节标题（中文）
    start: float                 # 开始时间（秒）
    end: float                   # 结束时间（秒）
    segment_indices: list[int]   # 对应 transcript_segments 中的索引范围
    summary_zh: str              # 中文摘要（summarize_chapters 填充）


class PodlatorState(TypedDict, total=False):
    """Pipeline 全局状态。节点返回 partial dict，LangGraph 自动合并。

    字段标注 Annotated[type, reducer] 的字段使用 reducer 合并：
    - operator.add: 数值累加（total_cost_usd）
    - _merge_dicts: dict 浅合并（node_durations_ms）
    """

    # ── 身份标识（创建时设定）──
    task_id: str                 # UUID4 字符串
    source_url: str              # 输入的 URL

    # ── 元数据（fetch_metadata 产出）──
    title: str                   # 视频/播客标题
    description: str             # 描述
    duration_seconds: float      # 总时长（秒）
    published_at: str            # 发布时间 ISO 8601
    source_type: str             # "youtube" | "podcast_rss"
    thumbnail_url: str           # 封面图 URL

    # ── 音频（download_audio 产出）──
    audio_path: str              # 本地音频文件绝对路径
    audio_format: str            # "mp3" | "m4a" | "wav"
    audio_size_bytes: int        # 文件大小

    # ── 转写（transcribe 产出）──
    transcript_segments: list[TranscriptSegment]
    transcript_text: str         # 全文拼接（便于 LLM 处理）
    stt_provider: str            # "deepgram" | "tencent_cloud" | "mlx_whisper"
    has_diarization: bool        # STT 是否已带说话人标签

    # ── 说话人分离（diarize 产出，可选）──
    # 直接更新 transcript_segments 中的 speaker 字段

    # ── 章节（chapter_split 产出）──
    chapters: list[Chapter]

    # ── 摘要（summarize_chapters 产出）──
    chapter_summaries: list[str] # 各章节中文摘要（中间产物）

    # ── 简报（polish_final 产出）──
    brief_markdown: str          # 最终润色后的完整 Markdown 简报

    # ── 导出（export_markdown 产出）──
    output_path: str             # 导出的 .md 文件路径

    # ── 控制字段 ──
    current_node: str            # 当前执行到的节点名
    status: str                  # "pending" | "running" | "completed" | "failed"
    error: str | None            # 失败时的错误信息
    node_durations_ms: Annotated[dict[str, float], _merge_dicts]  # 各节点耗时（毫秒）
    total_cost_usd: Annotated[float, operator.add]                # 累计 API 费用（美元）
    created_at: str              # 创建时间 ISO 8601
    updated_at: str              # 最后更新时间 ISO 8601
```

### 节点 → State 字段映射

| 节点 | 读取字段 | 写入字段 |
|---|---|---|
| `fetch_metadata` | `source_url` | `title`, `description`, `duration_seconds`, `published_at`, `source_type`, `thumbnail_url` |
| `download_audio` | `source_url`, `task_id` | `audio_path`, `audio_format`, `audio_size_bytes` |
| `transcribe` | `audio_path` | `transcript_segments`, `transcript_text`, `stt_provider`, `has_diarization`, `total_cost_usd` (reducer 累加) |
| `diarize` | `transcript_segments`, `has_diarization` | `transcript_segments`（更新 speaker 字段）|
| `chapter_split` | `transcript_text`, `transcript_segments` | `chapters`, `total_cost_usd` (reducer 累加) |
| `summarize_chapters` | `chapters`, `transcript_segments` | `chapter_summaries`, `chapters`（填充 summary_zh）, `total_cost_usd` (reducer 累加) |
| `polish_final` | `title`, `chapters`, `chapter_summaries` | `brief_markdown`, `total_cost_usd` (reducer 累加) |
| `export_markdown` | `brief_markdown`, `task_id`, `title` | `output_path` |

### Graph 执行流

```
fetch_metadata → download_audio → transcribe → [条件] → chapter_split
                                                  │
                                    has_diarization?
                                    ├─ True  → 跳过 diarize
                                    └─ False → diarize → chapter_split

chapter_split → summarize_chapters → polish_final → export_markdown
```

---

## 3. Provider 接口

### 3.1 STTProvider

```python
"""src/podlator/providers/stt/base.py"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from podlator.graph.state import TranscriptSegment


@dataclass
class STTResult:
    """转写结果。"""

    segments: list[TranscriptSegment]
    full_text: str
    has_diarization: bool
    provider_name: str
    duration_ms: float
    cost_usd: float


class STTProvider(ABC):
    """STT 转写 Provider 接口。"""

    @abstractmethod
    async def transcribe(
        self,
        audio_path: Path,
        *,
        language: str = "en",
        diarize: bool = True,
    ) -> STTResult:
        """转写音频文件，返回带时间戳的片段。"""
        ...
```

**M0**: 只有 base.py，不写具体实现。
**M1**: 实现 `DeepgramProvider`。
**腾讯云扩展**: 实现 `TencentCloudProvider`，通过 COS 暂存音频并以预签名 URL 调用录音文件识别。
**M4**: 实现 `MLXWhisperProvider`。

### 3.2 LLMProvider

```python
"""src/podlator/providers/llm/base.py"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResult:
    """LLM 调用结果。"""

    content: str
    model: str
    provider_name: str
    tokens_in: int
    tokens_out: int
    duration_ms: float
    cost_usd: float


class LLMProvider(ABC):
    """LLM Provider 接口。"""

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 8192,
    ) -> LLMResult:
        """发送 prompt，返回补全结果。"""
        ...
```

**M0**: 只有 base.py。
**M1**: 实现 `DeepSeekProvider` + `ClaudeProvider`（两者都用 OpenAI SDK，走 OpenAI 兼容 API）。

### 3.3 DownloaderProvider

```python
"""src/podlator/providers/downloader/base.py"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DownloadResult:
    """下载结果。"""

    file_path: Path
    format: str
    size_bytes: int
    duration_seconds: float


@dataclass
class MediaMetadata:
    """媒体元数据。"""

    title: str
    description: str
    duration_seconds: float
    published_at: str
    source_type: str          # "youtube" | "podcast_rss"
    thumbnail_url: str


class DownloaderProvider(ABC):
    """音频下载 Provider 接口。"""

    @abstractmethod
    async def download(
        self,
        url: str,
        *,
        output_dir: Path,
        audio_format: str = "mp3",
    ) -> DownloadResult:
        """下载音频文件到本地。"""
        ...

    @abstractmethod
    async def fetch_metadata(self, url: str) -> MediaMetadata:
        """获取媒体元数据（不下载文件）。"""
        ...
```

**M0**: 只有 base.py。
**M1**: 实现 `YtDlpDownloader`。

---

## 4. 数据库 Schema

```sql
-- 参考 SQL，实际由 Python 代码创建

CREATE TABLE IF NOT EXISTS tasks (
    id              TEXT PRIMARY KEY,                  -- UUID4
    source_url      TEXT NOT NULL,                     -- 输入 URL
    title           TEXT,                              -- 媒体标题
    status          TEXT NOT NULL DEFAULT 'pending',   -- pending/running/completed/failed
    current_node    TEXT,                              -- 当前执行节点
    error_message   TEXT,                              -- 失败信息
    brief_path      TEXT,                              -- 输出 .md 路径
    audio_path      TEXT,                              -- 音频文件路径
    cost_usd        REAL NOT NULL DEFAULT 0.0,         -- 累计费用
    duration_seconds REAL,                             -- 媒体时长
    created_at      TEXT NOT NULL,                     -- ISO 8601
    updated_at      TEXT NOT NULL                      -- ISO 8601
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
```

### TaskStore 接口

```python
"""src/podlator/storage/db.py 核心方法"""

class TaskStore:
    """SQLite 任务存储。使用 aiosqlite 异步访问。"""

    async def initialize(self) -> None:
        """创建表（如不存在）。"""

    async def create(self, task_id: str, source_url: str) -> dict:
        """创建新任务，返回完整记录。"""

    async def get(self, task_id: str) -> dict | None:
        """按 ID 查询任务，不存在返回 None。"""

    async def list_tasks(
        self,
        *,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        """查询任务列表，支持按 status 过滤和分页。"""

    async def update(self, task_id: str, **fields: Any) -> dict:
        """更新任务字段，返回更新后的记录。"""

    async def delete(self, task_id: str) -> bool:
        """删除任务，返回是否删除成功。"""
```

---

## 5. API 路由

### REST 路由

| 方法 | 路径 | 请求体/参数 | 响应 | 说明 |
|---|---|---|---|---|
| `POST` | `/api/tasks` | `{ "url": "https://..." }` | `201 { task_id, status }` | 创建任务 |
| `GET` | `/api/tasks` | `?status=&limit=20&offset=0` | `200 [{ task_id, title, status, ... }]` | 任务列表 |
| `GET` | `/api/tasks/{task_id}` | — | `200 { task_id, title, status, ... }` | 任务详情 |
| `DELETE` | `/api/tasks/{task_id}` | — | `204` | 删除任务 |
| `POST` | `/api/tasks/{task_id}/retry` | — | `200 { task_id, status }` | 重试失败任务 |
| `GET` | `/api/tasks/{task_id}/brief` | — | `200 { markdown: "..." }` | 获取简报内容 |
| `GET` | `/api/health` | — | `200 { status: "ok" }` | 健康检查 |

### WebSocket

| 路径 | 说明 |
|---|---|
| `WS /ws/tasks/{task_id}/logs` | 订阅任务实时日志（JSON Lines，每条一个 structlog 事件）|

### Pydantic 请求/响应模型

```python
"""src/podlator/api/schemas.py"""

class TaskCreate(BaseModel):
    url: HttpUrl

class TaskResponse(BaseModel):
    task_id: str
    source_url: str
    title: str | None
    status: str
    current_node: str | None
    error_message: str | None
    cost_usd: float
    created_at: str
    updated_at: str

class TaskBriefResponse(BaseModel):
    task_id: str
    title: str | None
    markdown: str

class HealthResponse(BaseModel):
    status: str = "ok"
```

### 错误响应格式

```json
{
  "detail": "Task not found",
  "error_code": "TASK_NOT_FOUND"
}
```

标准错误码：`TASK_NOT_FOUND`, `TASK_ALREADY_RUNNING`, `INVALID_URL`, `INTERNAL_ERROR`

---

## 6. CLI 接口

```
Usage: podlator [OPTIONS] COMMAND [ARGS]...

  Podlator — 英文播客/视频 → 中文简报

Commands:
  run      处理单个 URL，产出中文简报
  status   查看任务状态
  list     列出所有任务
  version  显示版本号

---

podlator run <url> [--output-dir PATH]
  处理 URL，默认输出到 data/briefs/

podlator status [TASK_ID]
  无参数时显示最近一个任务的状态

podlator list [--status pending|running|completed|failed] [--limit N]
  默认显示最近 20 个

podlator version
  输出 "podlator x.y.z"
```

实现使用 **Typer** 库，入口配置在 `pyproject.toml` 的 `[project.scripts]`。

---

## 7. 配置项完整列表

```python
"""src/podlator/config.py"""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。从 .env 文件加载，环境变量覆盖。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # ── API Keys ──
    deepgram_api_key: str = ""
    deepseek_api_key: str = ""
    claude_api_key: str = ""               # 第三方平台 API Key

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
    deepseek_model: str = "deepseek-v4-flash"  # 1M 上下文
    deepseek_max_tokens: int = 8192             # 输出 token 上限

    # ── Claude（第三方平台，OpenAI 兼容 API）──
    claude_base_url: str = "https://api.b.ai/v1"
    claude_model: str = "claude-opus-4.7"
    claude_max_tokens: int = 4096               # 输出 token 上限

    # ── Deepgram ──
    deepgram_model: str = "nova-3"
    deepgram_language: str = "en"
```

---

## 8. 文件路径约定

```
data/                                    # 运行时数据（.gitignore）
├── podlator.db                          # SQLite 主库
├── checkpoints.sqlite                   # LangGraph checkpoint
├── audio/
│   └── {task_id}/
│       └── audio.mp3                    # 下载的音频
├── briefs/
│   └── {task_id}/
│       └── {title_slug}.md              # 输出简报
├── artifacts/
│   └── {task_id}/
│       ├── 00_pipeline.log.jsonl        # 节点完成/失败事件与产物清单
│       ├── 01_source.json               # 原始链接与任务信息
│       ├── 02_metadata.json             # 标题、时长、发布时间等
│       ├── 03_audio.* / 03_audio.json   # 音频副本与音频路径/大小
│       ├── 04_transcript.*              # 转写文本与分段 JSON
│       ├── 05_chapters.*                # 章节切分结果
│       ├── 06_chapter_summaries.*       # 章节摘要结果
│       ├── 07_polished_brief.md         # 润色后的最终简报内容
│       └── 08_export.json               # 导出文件路径
└── logs/
    └── podlator.log                     # JSON 日志（追加写）
```

---

## 9. 节点列表

| 节点 | 文件 | 职责 | 主要依赖 | 实现阶段 |
|---|---|---|---|---|
| `fetch_metadata` | `nodes/fetch_metadata.py` | 获取标题、时长、发布时间 | DownloaderProvider | M1 |
| `download_audio` | `nodes/download_audio.py` | 下载音频到本地 | DownloaderProvider | M1 |
| `transcribe` | `nodes/transcribe.py` | STT 转写 | STTProvider | M1 |
| `diarize` | `nodes/diarize.py` | 说话人分离（条件执行） | pyannote.audio | M4 |
| `chapter_split` | `nodes/chapter_split.py` | 按主题切分章节 | LLMProvider | M1 |
| `summarize_chapters` | `nodes/summarize_chapters.py` | 章节翻译+精简（并发） | LLMProvider | M1 |
| `polish_final` | `nodes/polish_final.py` | 全局润色，加引言/结论 | LLMProvider | M1 |
| `export_markdown` | `nodes/export_markdown.py` | 导出 .md 文件 | — | M1 |

M0 阶段：所有节点只有占位实现（`return {}`），但文件结构和测试完整。

---

## 10. 前端路由（M2 实现，M0 仅占位页面组件）

| 路径 | 页面组件 | 说明 |
|---|---|---|
| `/` | `SubmitPage` | 输入 URL 提交任务 |
| `/queue` | `QueuePage` | 任务列表 + 状态筛选 |
| `/tasks/:id` | `TaskDetailPage` | 实时日志 + 进度展示 |
| `/tasks/:id/brief` | `BriefViewerPage` | 查看/导出简报 |
