# Podlator

> Podcast + Translator + Curator — 把英文播客和 YouTube 视频播客自动转写、精简翻译成高质量中文简报。

Podlator 是一个自用工具，解决一个具体问题：**英文播客和长视频信息密度高但消费成本高**。让 AI 处理它们，产出可快速阅读的中文简报，保留原文存档备查。

## 它做什么

```
投喂 URL（手动 / RSS / YouTube）
    ↓
下载音频
    ↓
转写（带说话人分离）
    ↓
切分章节
    ↓
中文精简翻译（DeepSeek 主力）
    ↓
全局润色（Claude 精修引言/结论）
    ↓
导出 Markdown 简报（含原文转录附录）
    ↓
（未来）TTS 生成中文播报音频
```

## 设计原则

- **状态机驱动**：基于 LangGraph，每期播客是一个 State，节点是一次转换，**支持断点续传**
- **可观察性优先**：所有节点输出结构化日志，Web UI 实时展示每一步进展
- **可测试性优先**：每个节点是纯函数（输入 State，输出 patch），独立可测试
- **可演进性优先**：Provider 接口隔离，切换 STT / LLM 是改配置不是改代码
- **混合策略**：云 API 优先（信达雅 + 省事），本地推理可切换（学习 MLX + 兜底）
- **自用单机**：SQLite + 本地文件系统，零运维

## 技术栈

| 层 | 选型 | 理由 |
|---|---|---|
| 编排核心 | **LangGraph (Python)** | 状态机原生支持，checkpoint 持久化，节点流式输出 |
| Web 后端 | **FastAPI + WebSocket** | 异步性能好，与 LangGraph 同生态 |
| Web 前端 | **Vite + React + TanStack Query + shadcn/ui** | 用户的强项栈，shadcn 适合自用工具 |
| 存储 | **SQLite + 本地文件系统** | 零运维，单机够用，未来要换换连接串即可 |
| 日志 | **structlog** | 结构化日志事实标准，Web UI 解析友好 |
| 测试 | **pytest + pytest-asyncio + vitest** | 后端 Python 测试 + 前端 TS 测试 |
| 包管理 | **uv (Python) + pnpm (前端)** | 现代化、快速 |

### 外部服务

| 用途 | 主力 | 备选 |
|---|---|---|
| STT 转写 | Deepgram Nova-3（云） / 腾讯云 ASR 大模型版（COS URL）| mlx-whisper（本地，Milestone 4） |
| 章节切分 + 翻译 | DeepSeek V4-Flash（1M 上下文）| — |
| 全局润色 | Claude Opus 4.7（第三方平台）| DeepSeek（fallback） |
| TTS（未来）| 火山引擎 | IndexTTS（本地） |

**成本预算**：单期 1 小时英文播客约 ¥1 元，预算上限 5 元/期。

## 快速开始

### 前置要求

- Python 3.12+
- Node.js 20+
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- `pnpm`（`npm install -g pnpm`）
- `ffmpeg`（`brew install ffmpeg`）

### 安装

```bash
# 后端
uv sync

# 前端
cd web && pnpm install && cd ..

# 配置
cp .env.example .env
# 编辑 .env 填入 DEEPGRAM_API_KEY / DEEPSEEK_API_KEY / CLAUDE_API_KEY
# 如使用腾讯云 ASR，把 STT_PROVIDER 设为 tencent_cloud 并填入 TENCENT_* 配置
```

### 运行单次任务（CLI）

```bash
uv run podlator run "https://www.youtube.com/watch?v=XXXXX"
```

### 启动 Web UI

```bash
# 终端 1：后端
uv run uvicorn podlator.api.main:app --reload --port 8000

# 终端 2：前端
cd web && pnpm dev
```

访问 http://localhost:5173

## 项目结构

```
podlator/
├── src/podlator/                # Python 后端
│   ├── config.py                # pydantic-settings 配置加载
│   ├── logging.py               # structlog 结构化日志
│   ├── errors.py                # 统一异常类型
│   ├── graph/                   # LangGraph pipeline
│   │   ├── state.py             # PodlatorState 定义
│   │   ├── builder.py           # Graph 组装
│   │   └── nodes/               # 各节点（每个文件一个节点）
│   ├── providers/               # 外部服务适配器
│   │   ├── stt/                 # STTProvider 接口 + 实现
│   │   ├── llm/                 # LLMProvider 接口 + 实现
│   │   └── downloader/          # yt-dlp / RSS
│   ├── storage/                 # SQLite + 文件路径管理
│   ├── api/                     # FastAPI 路由 + WebSocket
│   ├── prompts/                 # Prompt 模板（Markdown 文件）
│   └── cli.py                   # Typer CLI 入口
├── tests/
│   ├── unit/                    # 节点 / Provider 单测
│   ├── integration/             # 端到端集成测试
│   └── fixtures/                # 测试音频 + 样本数据
├── web/                         # 前端
│   └── src/
│       ├── pages/               # Submit / Queue / TaskDetail / BriefViewer
│       ├── components/
│       └── lib/                 # API client + WebSocket
├── data/                        # 运行时数据（gitignore）
│   ├── podlator.db              # SQLite 主库
│   ├── checkpoints.sqlite       # LangGraph checkpoint
│   ├── audio/                   # 下载的音频
│   ├── briefs/                  # 输出的 Markdown 简报
│   ├── artifacts/               # 按 task_id 归档的中间产物与排查日志
│   └── logs/                    # JSON 日志文件
├── docs/                        # 设计文档
│   ├── ROADMAP.md
│   ├── ARCHITECTURE.md
│   ├── BRIEF_FORMAT.md
│   └── PROMPTS_GUIDE.md
├── scripts/                     # 辅助脚本
├── README.md                    # 本文件
├── CLAUDE.md                    # AI IDE 协作指南
├── CHANGELOG.md                 # 更新日志
└── pyproject.toml
```

## LangGraph 状态机

整个 pipeline 是一个状态机。**State** 见 `src/podlator/graph/state.py`，**节点列表**：

| 节点 | 输入 | 输出 | 主要依赖 |
|---|---|---|---|
| `fetch_metadata` | URL | 标题、时长、发布时间 | yt-dlp / feedparser |
| `download_audio` | URL | 本地音频路径 | yt-dlp |
| `transcribe` | 音频路径 | 带时间戳的转写片段 | Deepgram / 腾讯云 ASR / mlx-whisper |
| `diarize` | 转写片段 | 说话人标签（如未自带） | pyannote.audio |
| `chapter_split` | 转写全文 | 章节切片 | DeepSeek |
| `summarize_chapters` | 章节切片 | 各章节中文摘要 | DeepSeek（并发）|
| `polish_final` | 章节摘要 | 最终简报 Markdown | Claude Opus 4.7 |
| `export_markdown` | 简报内容 | MD 文件路径 | — |

执行顺序、条件分支（如 STT 已带说话人就跳过 diarize）见 `src/podlator/graph/builder.py`。

## 开发约定

- **每次新功能开发**：
  1. 先写或更新测试
  2. 跑通测试：`uv run pytest`
  3. 更新 `CHANGELOG.md`
  4. 必要时更新 `README.md` / `CLAUDE.md`
- **每个节点必须有单元测试**，外部 API 用 mock
- **所有 `logger.info()` 调用必须带 `task_id` 上下文**
- **Prompt 写在 `src/podlator/prompts/` 下，不要硬编码在代码里**
- **提交信息用约定式提交**：`feat(graph): ...`、`fix(stt): ...`、`docs: ...`、`test: ...`

## 路线图（精简版）

完整版见 [`docs/ROADMAP.md`](./docs/ROADMAP.md)。

- **M0** 项目骨架（配置、日志、状态机、节点占位、测试框架）
- **M1** 核心 pipeline 跑通（CLI 投喂 URL → 产出 Markdown 简报）
- **M2** Web UI MVP（投喂、队列、实时日志、简报浏览）
- **M3** 质量提升（Prompt 工程、说话人命名、术语一致性）
- **M4** 本地 STT 兜底（mlx-whisper + pyannote）
- **M5** 自动化与分发（RSS 订阅、定时任务、RSS feed 输出）
- **M6** TTS（中文播报音频）

## 许可

私人项目，未开源。
