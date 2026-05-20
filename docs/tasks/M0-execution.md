# M0 执行手册 — 项目骨架搭建

> **本文件是给 AI CLI（Claude Code / Cursor）的逐步执行指南。**
> 按 Phase 顺序执行，每个 Phase 结束后运行验证命令，全部通过再进入下一个。
>
> 规格细节参考 `docs/ARCHITECTURE.md`。代码规范参考 `CLAUDE.md`。

---

## 约定

- 项目根目录: 当前工作目录（包含 README.md 和 CLAUDE.md 的那个目录）
- Python 版本: >= 3.12
- 包管理: uv（Python）、pnpm（前端）
- M0 不写任何真实业务逻辑，所有节点和 Provider 都是占位实现
- 所有新文件头部加 `from __future__ import annotations`
- 所有新文件第一行是模块 docstring

---

## Phase 1: 项目基础设施

### 1.1 创建 .gitignore

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
dist/
build/
.eggs/

# Virtual env
.venv/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Environment
.env

# Runtime data
data/

# OS
.DS_Store
Thumbs.db

# Test / Coverage
.coverage
htmlcov/
.pytest_cache/

# Frontend
web/node_modules/
web/dist/

# Logs（data/ 已覆盖，但以防万一）
*.log
```

### 1.2 创建 pyproject.toml

关键配置点:
- `[project]` 基本信息，`requires-python = ">=3.12"`
- `[project.scripts]` 注册 CLI 入口: `podlator = "podlator.cli:app"`
- `[tool.pytest.ini_options]` 配置 asyncio_mode = "auto", testpaths
- `[tool.ruff]` 配置 lint + format
- `[tool.mypy]` strict 模式
- `[tool.coverage]` 配置覆盖率

依赖列表（M0 就全部声明，即使暂时不用）:

**运行时依赖**:
- langgraph >= 0.3
- fastapi >= 0.115
- uvicorn[standard]
- pydantic >= 2.0
- pydantic-settings
- structlog
- httpx
- typer
- tenacity
- aiosqlite
- yt-dlp
- deepgram-sdk >= 3.0
- openai >= 1.0（DeepSeek + Claude 都用 OpenAI 兼容 API）

**开发依赖**（放在 `[dependency-groups]` 的 dev 组）:
- pytest
- pytest-asyncio
- pytest-httpx
- pytest-cov
- pytest-randomly
- ruff
- mypy
- time-machine

### 1.3 创建 .env.example

```env
# === Podlator 配置 ===
# 复制本文件为 .env，填入你的 API Key

# ── API Keys ──
DEEPGRAM_API_KEY=
DEEPSEEK_API_KEY=
CLAUDE_API_KEY=

# ── Provider 选择 ──
# STT_PROVIDER=deepgram            # deepgram | mlx_whisper
# LLM_PROVIDER_SUMMARIZE=deepseek
# LLM_PROVIDER_POLISH=claude

# ── 日志 ──
# LOG_LEVEL=INFO                   # DEBUG | INFO | WARNING | ERROR
# LOG_JSON_ENABLED=true

# ── DeepSeek（OpenAI 兼容 API）──
# DEEPSEEK_BASE_URL=https://api.deepseek.com
# DEEPSEEK_MODEL=deepseek-v4-flash
# DEEPSEEK_MAX_TOKENS=8192

# ── Claude（第三方平台，OpenAI 兼容 API）──
# CLAUDE_BASE_URL=https://api.b.ai/v1
# CLAUDE_MODEL=claude-opus-4.7
# CLAUDE_MAX_TOKENS=4096
```

### 1.4 创建 CHANGELOG.md

```markdown
# Changelog

所有重大变更记录在此文件。格式参考 [Keep a Changelog](https://keepachangelog.com/)。

## [Unreleased]

### Added
- 项目骨架搭建（M0）
- LangGraph 状态机 + 8 个占位节点
- Provider 接口定义（STT / LLM / Downloader）
- FastAPI + WebSocket 应用骨架
- Typer CLI 入口
- structlog 日志配置
- SQLite TaskStore
- pytest 测试基础设施
- Vite + React 前端骨架
```

### 1.5 验证

```bash
uv sync           # 应成功安装所有依赖
uv run python -c "import podlator; print('OK')"  # 这一步可能还不通过（包还没建），先确认 uv sync 成功即可
```

---

## Phase 2: Python 包核心模块

### 2.1 目录结构

创建以下所有 `__init__.py` 和核心模块文件:

```
src/podlator/
├── __init__.py              # 版本号: __version__ = "0.1.0"
├── config.py                # Settings 类（完整实现）
├── logging.py               # structlog 配置（完整实现）
├── errors.py                # NodeError 等异常类
├── graph/
│   ├── __init__.py
│   ├── state.py             # PodlatorState（按 ARCHITECTURE.md 定义）
│   ├── builder.py           # Graph 编译（占位）
│   └── nodes/
│       ├── __init__.py
│       └── _base.py         # @node 装饰器 + node_logger
├── providers/
│   ├── __init__.py
│   ├── stt/
│   │   ├── __init__.py
│   │   └── base.py          # STTProvider 接口（按 ARCHITECTURE.md）
│   ├── llm/
│   │   ├── __init__.py
│   │   └── base.py          # LLMProvider 接口
│   └── downloader/
│       ├── __init__.py
│       └── base.py          # DownloaderProvider 接口
├── storage/
│   ├── __init__.py
│   └── db.py                # TaskStore（完整实现 CRUD）
├── api/
│   ├── __init__.py
│   ├── main.py              # FastAPI app
│   ├── routes.py            # 路由（返回 501 占位）
│   ├── schemas.py           # Pydantic 请求/响应模型
│   └── ws.py                # WebSocket（占位）
├── prompts/                  # 空目录，放 .gitkeep
│   └── .gitkeep
└── cli.py                   # Typer CLI
```

### 2.2 config.py

按 `docs/ARCHITECTURE.md` 第 7 节的 Settings 类完整实现。这是真实代码，不是占位。

要点:
- 继承 `BaseSettings`
- 使用 `SettingsConfigDict(env_file=".env")`
- 所有字段有类型注解和默认值
- API key 默认空字符串（M0 不需要真实 key）

### 2.3 logging.py

实现 structlog 配置。这是真实代码。

要点:
- 提供 `get_logger(name)` 函数
- 提供 `setup_logging(log_level, json_enabled)` 初始化函数
- 开发模式: 彩色控制台输出（ConsoleRenderer）
- 生产模式: JSON 输出到文件 + 控制台
- 自动注入 timestamp
- 参考 `docs/OBSERVABILITY.md` 的输出格式

### 2.4 errors.py

```python
class PodlatorError(Exception):
    """基础异常。"""

class NodeError(PodlatorError):
    """节点执行失败。"""
    def __init__(self, node_name: str, message: str, *, retryable: bool = False):
        self.node_name = node_name
        self.retryable = retryable
        super().__init__(f"[{node_name}] {message}")

class ProviderError(PodlatorError):
    """外部 Provider 调用失败。"""
    def __init__(self, provider: str, message: str, *, retryable: bool = False):
        self.provider = provider
        self.retryable = retryable
        super().__init__(f"[{provider}] {message}")

class ConfigError(PodlatorError):
    """配置错误。"""
```

### 2.5 验证

```bash
uv run python -c "from podlator.config import Settings; s = Settings(); print(s.log_level)"
uv run python -c "from podlator.logging import get_logger; log = get_logger('test'); log.info('hello', x=1)"
uv run python -c "from podlator.errors import NodeError; raise NodeError('test', 'boom')" 2>&1 | head -5
```

---

## Phase 3: LangGraph State + 节点骨架

### 3.1 state.py

按 `docs/ARCHITECTURE.md` 第 2 节**原样**实现 `TranscriptSegment`、`Chapter`、`PodlatorState`。

### 3.2 nodes/_base.py

实现 `@node` 装饰器和 `node_logger` 工具函数。

`@node("name")` 装饰器应该:
- 自动设置 `state["current_node"] = name`
- 记录开始/结束日志（`node_started` / `node_completed`）
- 记录耗时到 `node_durations_ms`
- 捕获异常，包装为 `NodeError`，记录 `node_failed` 日志
- 返回 patch dict（自动注入 `current_node` 和 `node_durations_ms`）

`node_logger(state, node_name)` 应该:
- 返回一个绑定了 `task_id` 和 `node` 上下文的 structlog logger

### 3.3 8 个占位节点

在 `src/podlator/graph/nodes/` 下创建 8 个文件，每个遵循 CLAUDE.md 第 4 章的模板:

```
fetch_metadata.py
download_audio.py
transcribe.py
diarize.py
chapter_split.py
summarize_chapters.py
polish_final.py
export_markdown.py
```

每个节点的占位实现:

```python
"""节点：<一句话描述>。M0 占位实现。"""
from __future__ import annotations

from typing import Any

from podlator.graph.nodes._base import node, node_logger
from podlator.graph.state import PodlatorState


@node("node_name")
async def run(state: PodlatorState) -> dict[str, Any]:
    log = node_logger(state, "node_name")
    log.info("not_implemented", reason="M0 placeholder")
    return {}
```

> 替换 `node_name` 为实际名字，`一句话描述` 参考 ARCHITECTURE.md 第 9 节。

### 3.4 builder.py

实现 Graph 组装。M0 阶段需要能编译出一个可运行的 Graph。

要点:
- 使用 `StateGraph(PodlatorState)`
- 按 ARCHITECTURE.md 的执行流添加节点和边
- `transcribe` 之后有条件分支（`has_diarization`）
- 导出 `build_graph()` 函数，返回编译后的 graph
- M0 可以暂时线性连接（不加条件分支），只要能 `graph.compile()` 通过

### 3.5 验证

```bash
uv run python -c "
from podlator.graph.state import PodlatorState
from podlator.graph.builder import build_graph
g = build_graph()
print(f'Graph compiled: {type(g).__name__}')
print(f'Nodes: {list(g.nodes.keys()) if hasattr(g, \"nodes\") else \"OK\"}')
"
```

---

## Phase 4: Provider 接口

### 4.1 三个 base.py

按 `docs/ARCHITECTURE.md` 第 3 节**原样**实现:
- `src/podlator/providers/stt/base.py` — STTProvider + STTResult
- `src/podlator/providers/llm/base.py` — LLMProvider + LLMResult
- `src/podlator/providers/downloader/base.py` — DownloaderProvider + DownloadResult + MediaMetadata

注意: Result 类用 `@dataclass`，Provider 类用 `ABC`。

### 4.2 验证

```bash
uv run python -c "
from podlator.providers.stt.base import STTProvider, STTResult
from podlator.providers.llm.base import LLMProvider, LLMResult
from podlator.providers.downloader.base import DownloaderProvider, DownloadResult, MediaMetadata
print('All provider interfaces importable')
"
```

---

## Phase 5: Storage

### 5.1 db.py

实现 `TaskStore` 类，使用 `aiosqlite`。这是**真实实现**，不是占位。

要点:
- `__init__(self, db_path: str)` 接收数据库路径
- `async def initialize(self)` 创建表（用 ARCHITECTURE.md 第 4 节的 SQL）
- `async def create(self, task_id, source_url)` — 插入记录，设 created_at/updated_at 为当前 ISO 时间
- `async def get(self, task_id)` — 查询单条，返回 dict 或 None
- `async def list_tasks(self, *, status, limit, offset)` — 查询列表
- `async def update(self, task_id, **fields)` — 更新指定字段 + updated_at
- `async def delete(self, task_id)` — 删除记录
- 所有方法使用 `async with aiosqlite.connect(self.db_path) as db:` 连接
- 设置 `db.row_factory = aiosqlite.Row` 使结果可用 dict 访问

### 5.2 paths.py（可选，简单工具）

```python
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
```

### 5.3 验证

```bash
uv run python -c "
import asyncio
from podlator.storage.db import TaskStore

async def test():
    store = TaskStore(':memory:')
    await store.initialize()
    task = await store.create('test-id', 'https://example.com')
    print(f'Created: {task}')
    got = await store.get('test-id')
    print(f'Got: {got}')
    updated = await store.update('test-id', status='running', current_node='fetch_metadata')
    print(f'Updated: {updated}')
    tasks = await store.list_tasks()
    print(f'Listed: {len(tasks)} tasks')
    deleted = await store.delete('test-id')
    print(f'Deleted: {deleted}')
    print('All CRUD operations work!')

asyncio.run(test())
"
```

---

## Phase 6: API + CLI

### 6.1 api/schemas.py

按 ARCHITECTURE.md 第 5 节实现 Pydantic 模型:
- `TaskCreate`
- `TaskResponse`
- `TaskBriefResponse`
- `HealthResponse`

### 6.2 api/main.py

```python
"""FastAPI 应用入口。"""
from podlator.api.routes import router
# 创建 app，注册 router，添加 CORS middleware
# lifespan 中初始化 TaskStore
```

要点:
- 使用 lifespan 管理 TaskStore 生命周期（`app.state.store`）
- 注册 CORS（允许 `http://localhost:5173` 和 `http://localhost:3000`）
- mount router 到 `/api`

### 6.3 api/routes.py

M0 阶段的路由行为:
- `GET /api/health` → 返回 `{"status": "ok"}`（真实实现）
- `POST /api/tasks` → 创建任务记录到 SQLite，返回 201（真实实现）
- `GET /api/tasks` → 从 SQLite 查询列表（真实实现）
- `GET /api/tasks/{task_id}` → 从 SQLite 查询（真实实现）
- `DELETE /api/tasks/{task_id}` → 从 SQLite 删除（真实实现）
- `POST /api/tasks/{task_id}/retry` → 返回 501 Not Implemented（占位）
- `GET /api/tasks/{task_id}/brief` → 返回 501 Not Implemented（占位）

> 注意: task CRUD 在 M0 就是真实实现的（因为 TaskStore 已写好），只有 pipeline 执行和 brief 获取是占位。

### 6.4 api/ws.py

```python
"""WebSocket 日志推送。M0 占位。"""
from __future__ import annotations

from fastapi import APIRouter, WebSocket

router = APIRouter()


@router.websocket("/ws/tasks/{task_id}/logs")
async def task_logs(websocket: WebSocket, task_id: str) -> None:
    """订阅任务实时日志。M0 占位：接受连接后发送一条测试消息。"""
    await websocket.accept()
    await websocket.send_json({"event": "connected", "task_id": task_id, "message": "M0 placeholder"})
    # M1 实现：持续推送 structlog 事件
    await websocket.close()
```

### 6.5 cli.py

使用 Typer 实现 CLI:

```python
"""Podlator CLI 入口。"""
import typer

app = typer.Typer(help="Podlator — 英文播客/视频 → 中文简报")

@app.command()
def run(url: str, output_dir: str | None = None):
    """处理单个 URL，产出中文简报。"""
    typer.echo(f"[M0 占位] 将处理: {url}")
    # M1 实现：调用 LangGraph pipeline

@app.command()
def status(task_id: str | None = None):
    """查看任务状态。"""
    typer.echo("[M0 占位] 任务状态查询")

@app.command()
def list():
    """列出所有任务。"""
    typer.echo("[M0 占位] 任务列表")

@app.command()
def version():
    """显示版本号。"""
    from podlator import __version__
    typer.echo(f"podlator {__version__}")
```

### 6.6 验证

```bash
# CLI
uv run podlator --help
uv run podlator version
uv run podlator run "https://example.com"

# API（在另一个终端或用 timeout）
timeout 5 uv run uvicorn podlator.api.main:app --port 8000 &
sleep 2
curl -s http://localhost:8000/api/health | python3 -m json.tool
curl -s -X POST http://localhost:8000/api/tasks -H "Content-Type: application/json" -d '{"url":"https://example.com"}' | python3 -m json.tool
curl -s http://localhost:8000/api/tasks | python3 -m json.tool
kill %1 2>/dev/null
```

---

## Phase 7: 测试基础设施

### 7.1 目录结构

```
tests/
├── __init__.py
├── conftest.py              # 全局 fixtures
├── fixtures/
│   ├── audio/
│   │   └── .gitkeep         # M1 放真实音频
│   └── responses/
│       ├── deepgram_response.json     # mock API 响应
│       └── deepseek_response.json     # mock API 响应
├── unit/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_errors.py
│   ├── test_logging.py
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── test_state.py
│   │   ├── test_builder.py
│   │   └── nodes/
│   │       ├── __init__.py
│   │       ├── test_fetch_metadata.py
│   │       ├── test_download_audio.py
│   │       ├── test_transcribe.py
│   │       ├── test_diarize.py
│   │       ├── test_chapter_split.py
│   │       ├── test_summarize_chapters.py
│   │       ├── test_polish_final.py
│   │       └── test_export_markdown.py
│   ├── providers/
│   │   ├── __init__.py
│   │   └── test_provider_interfaces.py
│   ├── storage/
│   │   ├── __init__.py
│   │   └── test_db.py
│   └── api/
│       ├── __init__.py
│       └── test_routes.py
└── integration/
    ├── __init__.py
    └── test_graph_placeholder.py
```

### 7.2 conftest.py

全局 fixtures:

```python
"""全局测试 fixtures。"""
from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """确保测试不受真实 .env 影响。"""
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)


@pytest.fixture
def fixtures_dir() -> Path:
    """测试 fixtures 目录路径。"""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_state() -> dict:
    """最小可用的 PodlatorState。"""
    return {
        "task_id": "test-task-001",
        "source_url": "https://www.youtube.com/watch?v=test",
        "status": "pending",
        "current_node": "",
        "node_durations_ms": {},
        "total_cost_usd": 0.0,
    }
```

### 7.3 测试编写要求

**每个节点的测试至少包含**:
- `test_<node>_returns_dict` — 调用 run(state) 返回 dict
- `test_<node>_is_async` — 确认是异步函数

**core 模块测试**:
- `test_config.py` — Settings 能实例化、环境变量覆盖生效
- `test_errors.py` — NodeError / ProviderError 属性正确
- `test_logging.py` — get_logger 返回可用 logger

**storage 测试**:
- `test_db.py` — TaskStore 完整 CRUD 测试（用 `:memory:` 数据库）
  - test_create_task
  - test_get_task
  - test_get_nonexistent_task_returns_none
  - test_list_tasks
  - test_list_tasks_filter_by_status
  - test_update_task
  - test_delete_task
  - test_delete_nonexistent_task_returns_false

**API 测试**:
- `test_routes.py` — 用 httpx.AsyncClient 测 health、创建任务、列出任务
  - test_health_endpoint
  - test_create_task
  - test_list_tasks
  - test_get_task_not_found

**Integration 测试**:
- `test_graph_placeholder.py` — Graph 能编译并执行（M0 节点全部跳过也行）

### 7.4 mock 响应 fixtures

创建 `tests/fixtures/responses/` 下的 JSON 文件，供 M1 使用:

**deepgram_response.json**（简化版）:
```json
{
  "results": {
    "channels": [
      {
        "alternatives": [
          {
            "transcript": "Hello, welcome to the podcast.",
            "confidence": 0.98,
            "words": [
              {"word": "Hello", "start": 0.0, "end": 0.5, "confidence": 0.99, "speaker": 0},
              {"word": "welcome", "start": 0.6, "end": 1.0, "confidence": 0.98, "speaker": 0},
              {"word": "to", "start": 1.0, "end": 1.1, "confidence": 0.97, "speaker": 0},
              {"word": "the", "start": 1.1, "end": 1.2, "confidence": 0.99, "speaker": 0},
              {"word": "podcast", "start": 1.2, "end": 1.8, "confidence": 0.98, "speaker": 0}
            ]
          }
        ]
      }
    ]
  }
}
```

**deepseek_response.json**（OpenAI 格式）:
```json
{
  "id": "chatcmpl-test",
  "object": "chat.completion",
  "model": "deepseek-v4-flash",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "## 第一章：开场\n\n这期播客讨论了AI技术的最新进展。"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "total_tokens": 150
  }
}
```

### 7.5 验证

```bash
uv run pytest -v                                  # 应该全绿
uv run pytest --cov --cov-report=term-missing     # 查看覆盖率
uv run pytest --cov --cov-fail-under=70           # 覆盖率 >= 70%
```

---

## Phase 8: 代码质量检查

### 8.1 Ruff + Mypy

```bash
uv run ruff check .                  # 无错误
uv run ruff format --check .         # 格式正确
uv run mypy src/                     # 无类型错误
```

如果有错误，逐一修复。常见问题:
- 缺少 return type 注解
- `dict` 应该是 `dict[str, Any]`
- 异步函数缺少 `await`
- import 顺序不对（ruff 会自动修）

### 8.2 修复后再验证

```bash
uv run ruff format .                 # 自动格式化
uv run ruff check . --fix            # 自动修复可修的
uv run mypy src/                     # 再检查
uv run pytest                        # 确保修复没破坏测试
```

---

## Phase 9: 前端骨架

### 9.1 初始化 Vite + React + TypeScript

```bash
cd web     # 如果 web/ 不存在就先 mkdir web && cd web
pnpm create vite . --template react-ts
pnpm install
```

### 9.2 安装额外依赖

```bash
pnpm add react-router-dom @tanstack/react-query
pnpm add -D @types/react-router-dom
```

> shadcn/ui 在 M2 再集成，M0 只要有路由和空页面。

### 9.3 创建基础结构

```
web/src/
├── App.tsx              # 路由配置
├── main.tsx             # 入口（已有）
├── pages/
│   ├── SubmitPage.tsx
│   ├── QueuePage.tsx
│   ├── TaskDetailPage.tsx
│   └── BriefViewerPage.tsx
└── lib/
    └── api.ts           # API client 占位
```

**App.tsx** 配置 React Router，4 个路由指向 4 个空页面。

每个 Page 组件内容:
```tsx
export default function SubmitPage() {
  return <div><h1>Submit</h1><p>M0 placeholder</p></div>
}
```

### 9.4 验证

```bash
cd web && pnpm dev
# 浏览器访问 http://localhost:5173，应看到页面
# 访问 /queue、/tasks/123、/tasks/123/brief 应各显示对应占位页面
```

```bash
cd web && pnpm build    # 构建应成功
```

---

## Phase 10: 最终验证 + Git 提交

### 10.1 完整验证清单

从项目根目录依次运行:

```bash
# 1. 依赖
uv sync

# 2. 代码质量
uv run ruff check .
uv run ruff format --check .
uv run mypy src/

# 3. 测试
uv run pytest -v
uv run pytest --cov --cov-fail-under=70

# 4. CLI
uv run podlator --help
uv run podlator version

# 5. API（快速启动检查）
timeout 5 uv run uvicorn podlator.api.main:app --port 8000 &
sleep 2
curl -sf http://localhost:8000/api/health && echo " ✅ API health OK"
kill %1 2>/dev/null

# 6. 前端
cd web && pnpm build && echo "✅ Frontend build OK" && cd ..
```

### 10.2 Git 首次提交

```bash
git init
git add .
git commit -m "feat: M0 项目骨架搭建

- LangGraph 状态机 + 8 个占位节点
- Provider 接口定义（STT / LLM / Downloader）
- SQLite TaskStore（CRUD 完整实现）
- FastAPI 应用 + 路由（health + task CRUD）
- Typer CLI（run/status/list/version）
- structlog 日志配置（控制台 + JSON）
- pytest 基础设施（conftest + 占位测试）
- Vite + React 前端骨架（4 个页面占位）

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### 10.3 输出 DoD 自检

按 CLAUDE.md 第 13.6 节的格式输出完整的 DoD 自检结果。

---

## 常见问题

### Q: uv sync 失败怎么办？

检查 pyproject.toml 的依赖写法是否正确。常见错误:
- 依赖名拼错（如 `langgraph` 不是 `lang-graph`）
- 版本约束冲突

### Q: mypy 报很多类型错误怎么办？

M0 阶段优先修复 src/ 下的错误。常见问题:
- TypedDict 的 `total=False` 需要所有字段可选
- `dict` 需要写 `dict[str, Any]`
- 异步函数返回类型缺失

逐一修复，不要用 `# type: ignore` 除非真的不可避免。

### Q: 某个依赖在 Apple Silicon 上装不了？

用 `uv pip install --no-binary :all: <package>` 强制源码编译。
或暂时注释掉该依赖（如 pyannote.audio 在 M0 不需要），加注释说明 M4 时再启用。

### Q: 前端 pnpm create vite 出问题？

确保 Node.js >= 20。如果已有 web/ 目录但是空的，先删除再创建:
```bash
rm -rf web
pnpm create vite web --template react-ts
cd web && pnpm install
```
