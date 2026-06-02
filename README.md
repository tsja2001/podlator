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

### 单步文件转换 CLI

除了 `podlator run <url>` 一键跑完整 pipeline，每一步也可以**作为独立的文件转换命令**单独调用。
每个命令接受一个或多个输入文件，产出明确的输出文件，彼此不依赖任务状态或数据库。

设计理念：**每一步 = 明确的文件转换能力**，方便调试、复用和自由组合。

#### Pipeline 流程

```
URL ──→ download ──→ audio.mp3 ──→ transcribe ──→ transcript.json
                                         │
                           SRT 字幕 ──→ parse-srt ──→ transcript.json
                                                          │
                              assign-speakers ←──────────┘
                                    │
                                    ├──→ transcript.speakers.json
                                    │
                              split │
                                    ↓
                              chapters.json
                                    │
         ┌──────────────────────────┤
         │                          │
    render --mode summary      render --mode full
         │                          │
         ↓                          ↓
    summary.md                full-translation.md
         │
      polish
         │
         ↓
     brief.md
```

#### 命令概览

| 命令 | 输入 | 输出 | 需要 LLM | 需要外部服务 |
|---|---|---|---|---|
| `download` | URL | `.mp3` + `metadata.json` | — | yt-dlp |
| `transcribe` | `.mp3` | `transcript.json` | — | speech-transcriber CLI |
| `parse-srt` | `.srt` | `transcript.json` | — | — |
| `assign-speakers` | `transcript.json` | `transcript.json`（含 speaker） | ✅ | — |
| `split` | `transcript.json` | `chapters.json` | ✅ | — |
| `render` | `transcript.json` + `chapters.json` | `.md` | ✅ | — |
| `polish` | `.md` | `.md` | ✅ | — |

---

##### `download` — 下载音频

```
uv run podlator download <URL> -o <音频路径> [--metadata <JSON路径>]
```

| 参数 | 必需 | 说明 |
|---|---|---|
| `URL` | 是 | YouTube 或播客 RSS URL |
| `-o, --output` | 否 | 输出音频文件路径；省略则使用 yt-dlp 默认路径 |
| `--metadata` | 否 | 输出 metadata JSON 的路径，包含标题、时长、发布日期等 |

**输入**：一个 URL。

**生成文件**：
- **音频文件**（`.mp3` / `.m4a`）：下载的播客/视频音频
- **metadata JSON**（可选）：`title`、`description`、`duration_seconds`、`published_at`、`source_type`、`thumbnail_url`

> 示例：
> ```bash
> # 下载 YouTube 视频的音频，保存为 episode.mp3，同时把标题/时长等写入 meta.json
> uv run podlator download "https://www.youtube.com/watch?v=XXXXX" \
>   -o episode.mp3 \
>   --metadata meta.json
> ```

---

##### `transcribe` — 语音转文字

```
uv run podlator transcribe <音频文件> -o <JSON路径> [--provider <名称>] [--speech-transcriber-dir <目录>]
```

| 参数 | 必需 | 说明 |
|---|---|---|
| `AUDIO` | 是 | 音频文件路径（`.mp3` / `.m4a` / `.wav`） |
| `-o, --output` | 是 | 输出 Transcript JSON 路径 |
| `--provider` | 否 | Provider 名称，默认用 `SPEECH_TRANSCRIBER_PROVIDER` 配置 |
| `--speech-transcriber-dir` | 否 | speech-transcriber 项目目录，默认用 `SPEECH_TRANSCRIBER_PROJECT_DIR` 配置 |

**输入**：音频文件。**生成文件**：`transcript.json`（TranscriptDocument 格式，见下方）。

转写通过调用外部项目 `speech-transcriber` 的 CLI 完成，Podlator 本身不直接调用 ASR SDK。

> 示例：
> ```bash
> # 用腾讯云 ASR 将 episode.mp3 转写为 transcript.json
> uv run podlator transcribe episode.mp3 -o transcript.json --provider tencent_cloud
>
> # 用默认 provider（.env 中 SPEECH_TRANSCRIBER_PROVIDER 配置的值）
> uv run podlator transcribe episode.mp3 -o transcript.json
> ```

---

##### `parse-srt` — 解析字幕文件

```
uv run podlator parse-srt <SRT文件> -o <JSON路径> [--assign-speakers] [--source-url <URL>] [--title <标题>] [--llm-provider <名称>]
```

| 参数 | 必需 | 说明 |
|---|---|---|
| `SRT` | 是 | SRT 字幕文件路径 |
| `-o, --output` | 是 | 输出 Transcript JSON 路径 |
| `--assign-speakers` | 否 | 解析后继续调用 LLM 推断说话人标签 |
| `--source-url` | 否 | 写入 Transcript 的 `source.source_url` 字段 |
| `--title` | 否 | 写入 Transcript 的 `source.title` 字段 |
| `--llm-provider` | 否 | 配合 `--assign-speakers` 使用，指定 LLM |

**输入**：标准 SRT 字幕文件。**生成文件**：`transcript.json`（TranscriptDocument 格式）。

默认**不调用任何 LLM**，只做纯文本解析。传 `--assign-speakers` 时，解析完成后自动调用 LLM 推断说话人。

> 示例：
> ```bash
> # 纯解析 SRT → Transcript JSON，不调 LLM，不花钱
> uv run podlator parse-srt subtitles.srt -o transcript.json
>
> # 解析 SRT 的同时用 LLM 推断说话人，一步到位
> uv run podlator parse-srt subtitles.srt \
>   -o transcript.speakers.json \
>   --assign-speakers \
>   --title "Ep.42" \
>   --source-url "https://www.youtube.com/watch?v=XXXXX"
> ```

---

##### `assign-speakers` — 推断说话人

```
uv run podlator assign-speakers <Transcript JSON> -o <JSON路径> [--provider <名称>]
```

| 参数 | 必需 | 说明 |
|---|---|---|
| `TRANSCRIPT` | 是 | 输入的 Transcript JSON 路径 |
| `-o, --output` | 是 | 输出 Transcript JSON 路径 |
| `--provider` | 否 | LLM provider，默认用 `LLM_PROVIDER_SUMMARIZE` 配置 |

**输入**：`transcript.json`（TranscriptDocument 格式）。**生成文件**：`transcript.json`（同一格式，segments 的 `speaker` 字段被填充）。

行为约束：**只修改 `speaker` 字段**，不改写正文、时间戳或置信度。LLM 通过上下文线索推断说话人（非声纹级分离，结果应视为辅助标注）。

> 示例：
> ```bash
> # 用 LLM 推断每句话是谁说的，结果写入 transcript.speakers.json
> uv run podlator assign-speakers transcript.json -o transcript.speakers.json
>
> # 指定用 Claude 做说话人推断
> uv run podlator assign-speakers transcript.json \
>   -o transcript.speakers.json \
>   --provider claude
> ```

---

##### `split` — 切分章节

```
uv run podlator split <Transcript JSON> -o <JSON路径> [--provider <名称>]
```

| 参数 | 必需 | 说明 |
|---|---|---|
| `TRANSCRIPT` | 是 | 输入的 Transcript JSON 路径 |
| `-o, --output` | 是 | 输出 Chapters JSON 路径 |
| `--provider` | 否 | LLM provider，默认用 `LLM_PROVIDER_SUMMARIZE` 配置 |

**输入**：`transcript.json`（TranscriptDocument 格式）。**生成文件**：`chapters.json`（ChapterDocument 格式，`start/end + title`）。

行为约束：**只输出章节结构**，不翻译、不摘要、不润色正文。Prompt 使用 segments 中带时间戳的文本（`[0.00 - 5.25] speaker: text`），保证章节边界精确。

> 示例：
> ```bash
> # 将 transcript.json 按主题切分为章节，每章含起止时间和中文标题
> uv run podlator split transcript.json -o chapters.json
>
> # 指定用 DeepSeek 做章节切分
> uv run podlator split transcript.json -o chapters.json --provider deepseek
> ```

---

##### `render` — 渲染输出

```
uv run podlator render <Transcript JSON> --chapters <Chapters JSON> --mode <summary|full> -o <MD路径> [--provider <名称>]
```

| 参数 | 必需 | 说明 |
|---|---|---|
| `TRANSCRIPT` | 是 | 输入的 Transcript JSON 路径 |
| `--chapters` | 是 | Chapters JSON 路径 |
| `--mode` | 是 | 输出模式：`summary`（精简摘要）或 `full`（全文翻译） |
| `-o, --output` | 是 | 输出 Markdown 路径 |
| `--provider` | 否 | LLM provider，默认用 `LLM_PROVIDER_SUMMARIZE` 配置 |

**输入**：`transcript.json` + `chapters.json`。**生成文件**：Markdown 文件。

两种模式：
- **`summary`**：按章节生成中文精简摘要，压缩信息密度，适合快速浏览
- **`full`**：按章节输出完整中文翻译，不压缩信息，保留原文表达

> 示例：
> ```bash
> # 生成中文精简摘要（按章节压缩，适合快速浏览）
> uv run podlator render transcript.json \
>   --chapters chapters.json \
>   --mode summary \
>   -o summary.md
>
> # 生成中文全文翻译（不压缩，按章节完整翻译）
> uv run podlator render transcript.json \
>   --chapters chapters.json \
>   --mode full \
>   -o full.md
>
> # 用 Claude 做全文翻译
> uv run podlator render transcript.json \
>   --chapters chapters.json \
>   --mode full \
>   --provider claude \
>   -o full-claude.md
> ```

---

##### `polish` — 润色草稿

```
uv run podlator polish <Markdown草稿> -o <MD路径> [--title <标题>] [--provider <名称>]
```

| 参数 | 必需 | 说明 |
|---|---|---|
| `DRAFT` | 是 | 输入的 Markdown 草稿路径 |
| `-o, --output` | 是 | 输出 Markdown 路径 |
| `--title` | 否 | 节目标题，用于生成引言/结论 |
| `--provider` | 否 | LLM provider，默认用 `LLM_PROVIDER_POLISH` 配置 |

**输入**：Markdown 草稿（通常是 `render --mode summary` 的输出）。**生成文件**：润色后的 Markdown。

负责全局润色：修正翻译腔、统一术语、生成引言和结论。不改变章节结构。

> 示例：
> ```bash
> # 润色摘要草稿：修正翻译腔、统一术语、生成引言和结论
> uv run podlator polish summary.md -o brief.md
>
> # 带标题润色，LLM 会在引言中引用标题信息
> uv run podlator polish summary.md \
>   -o brief.md \
>   --title "Ep.42 — The Future of AI"
>
> # 用 Claude 做润色（.env 中 LLM_PROVIDER_POLISH 的默认值就是 claude）
> uv run podlator polish summary.md -o brief.md --provider claude
> ```

---

#### 中间文件格式

所有 step 之间通过两个标准 JSON 格式交互。

**Transcript JSON** (`transcript.json`)：

```json
{
  "schema_version": 1,
  "source": {
    "audio_path": "episode.mp3",
    "source_url": "https://www.youtube.com/watch?v=XXXXX",
    "title": "Episode Title",
    "duration_seconds": 1234.5
  },
  "provider": { "name": "tencent_cloud", "cost_usd": 0.01 },
  "text": "Full transcript text...",
  "segments": [
    {
      "index": 0,
      "start": 0.0,
      "end": 5.25,
      "speaker": "SPEAKER_0",
      "text": "Welcome to the show.",
      "confidence": 0.98
    }
  ]
}
```

**Chapters JSON** (`chapters.json`)：

```json
{
  "schema_version": 1,
  "source_transcript": "transcript.json",
  "chapters": [
    {
      "index": 0,
      "title": "开场与主题介绍",
      "start": 0.0,
      "end": 120.5,
      "segment_indices": [0, 1, 2, 3]
    }
  ]
}
```

#### 典型工作流

以下示例演示了 Podlator 在实际使用中的几种常见路径。

---

##### 场景 1：一键全自动 — 从 YouTube URL 到最终简报

适合"我就想看看结果"的情况。一条命令跑完整条 pipeline，中间产物保存在 `data/artifacts/{task_id}/` 下。

```bash
# 投喂一个 YouTube 链接，自动下载 → 转写 → 切章节 → 摘要 → 润色 → 导出 Markdown
uv run podlator run "https://www.youtube.com/watch?v=XXXXX"
```

完成后终端会打印简报文件路径和总费用。

---

##### 场景 2：逐步调试 — 从 URL 出发，每步检查中间产物

适合调试 prompt、检查转录质量、调整章节切分、对比 summary vs full。

```bash
# 1️⃣ 下载音频 + 元数据
#    URL → episode.mp3 + meta.json（含标题、时长、发布日期）
uv run podlator download "https://www.youtube.com/watch?v=XXXXX" \
  -o episode.mp3 \
  --metadata meta.json

# 2️⃣ 语音转文字
#    episode.mp3 → transcript.json（含带时间戳的 segments + 全文）
uv run podlator transcribe episode.mp3 -o transcript.json

# 3️⃣ 切分章节
#    transcript.json → chapters.json（每个章节的 start/end + 中文标题）
uv run podlator split transcript.json -o chapters.json

# 4️⃣ 生成中文精简摘要
#    transcript.json + chapters.json → summary.md（按章节的中文要点）
uv run podlator render transcript.json \
  --chapters chapters.json \
  --mode summary \
  -o summary.md

# 5️⃣ 全局润色
#    summary.md → brief.md（修正翻译腔、统一术语、补引言/结论）
uv run podlator polish summary.md -o brief.md

# 可选：顺便生成一份全文翻译
uv run podlator render transcript.json \
  --chapters chapters.json \
  --mode full \
  -o full-translation.md
```

---

##### 场景 3：从已有 SRT 字幕出发 — 不需要下载和转写

适合已经有字幕文件（如 YouTube 自动生成字幕、B站字幕）的情况。

```bash
# 1️⃣ 解析 SRT 字幕 → Transcript JSON（纯解析，不调 LLM）
uv run podlator parse-srt subtitles.srt \
  -o transcript.json \
  --title "Ep.42 — The Future of AI" \
  --source-url "https://www.youtube.com/watch?v=XXXXX"

# 或者一步到位：解析字幕的同时让 LLM 推断说话人
uv run podlator parse-srt subtitles.srt \
  -o transcript.speakers.json \
  --assign-speakers \
  --title "Ep.42 — The Future of AI"

# 2️⃣ 如果第 1 步没开 --assign-speakers，可以单独补做说话人推断
#    transcript.json → transcript.sp.json（只补充 speaker 字段）
uv run podlator assign-speakers transcript.json -o transcript.sp.json

# 3️⃣ 切分章节 → chapters.json
uv run podlator split transcript.sp.json -o chapters.json

# 4️⃣ 渲染为中文全文翻译
#    transcript.sp.json + chapters.json → full.md
uv run podlator render transcript.sp.json \
  --chapters chapters.json \
  --mode full \
  -o full.md

# 5️⃣ （可选）对全文翻译做润色
uv run podlator polish full.md -o full-polished.md
```

---

##### 场景 4：更换章节切分策略 — 复用已有转录，只重跑 split + render

适合"章节切得不对，换个 provider 或调整 prompt 重试"的情况。

```bash
# 已有 transcript.json，重新切分章节
uv run podlator split transcript.json -o chapters-v2.json

# 对比新旧章节
diff <(cat chapters.json | python -m json.tool) \
     <(cat chapters-v2.json | python -m json.tool)

# 用新章节重新生成摘要
uv run podlator render transcript.json \
  --chapters chapters-v2.json \
  --mode summary \
  -o summary-v2.md
```

---

##### 场景 5：双输出 — 同一期内容同时出精简简报和全文翻译

适合"既要快餐版快速浏览，又要存档版完整翻译"的情况。

```bash
# 前几步共享
uv run podlator download "https://www.youtube.com/watch?v=XXXXX" -o episode.mp3
uv run podlator transcribe episode.mp3 -o transcript.json
uv run podlator split transcript.json -o chapters.json

# 分叉 A：精简简报（适合分享/快速阅读）
uv run podlator render transcript.json \
  --chapters chapters.json \
  --mode summary \
  -o summary.md
uv run podlator polish summary.md -o brief.md

# 分叉 B：全文翻译（适合存档/深度阅读）
uv run podlator render transcript.json \
  --chapters chapters.json \
  --mode full \
  -o full-translation.md
```

---

##### 场景 6：对比不同 LLM 的渲染效果

适合评估 DeepSeek vs Claude 对同一内容的中文翻译质量。

```bash
# 用 DeepSeek（默认）生成全文翻译
uv run podlator render transcript.json \
  --chapters chapters.json \
  --mode full \
  -o full-deepseek.md

# 用 Claude 生成全文翻译做对比
uv run podlator render transcript.json \
  --chapters chapters.json \
  --mode full \
  --provider claude \
  -o full-claude.md

# 用 diff 对比差异
diff full-deepseek.md full-claude.md
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
│   ├── steps/                   # 文件转换型业务能力（CLI + Graph 共享）
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
| `transcribe` | 音频路径 | 带时间戳的转写片段 | speech-transcriber CLI（腾讯云 ASR / Deepgram / mlx-whisper）|
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
