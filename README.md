# Podlator

Podlator 是一个自用的英文播客 / YouTube 视频播客中文化工具。

当前最常用的用途是：把已经下载好的英文字幕整理成中文口播稿，再用外部 TTS 生成中文播客音频。项目里也保留了早期的中文简报、全文翻译、URL 下载和音频转写能力。

## 当前主工作流：英文字幕生成中文播客

现在实际跑通的链路是：

```text
手动下载英文 SRT 字幕
  -> parse-srt            # 字幕转标准 Transcript JSON
  -> assign-speakers      # 可选：LLM 推断说话人
  -> douyin-script        # 生成中文口播/解说稿
  -> 手动整理标题、简介、开场白
  -> speech-transcriber   # 开场白和正片分别 TTS
  -> 手动拼接 MP3
```

其中 Podlator 负责前半段文本处理；TTS 和音频拼接目前不在 Podlator 内置 pipeline 中。

### 1. 准备字幕

先手动下载英文 SRT 字幕，放在 `project/` 下对应节目目录中，例如：

```text
project/08How Microsoft thinks about AGI/Satya Nadella – How Microsoft thinks about AGI.srt
```

### 2. 一键生成中文口播稿

推荐直接使用 `pipeline-douyin`：

```bash
uv run podlator pipeline-douyin \
  "project/08How Microsoft thinks about AGI/Satya Nadella – How Microsoft thinks about AGI.srt" \
  -o "project/08How Microsoft thinks about AGI/抖音剪辑版/抖音解说稿_Microsoft_AGI.md" \
  --title "Satya Nadella - How Microsoft is preparing for AGI"
```

它会自动执行：

```text
parse-srt -> assign-speakers -> douyin-script
```

默认两段式生成约 6000 字口播稿：便宜模型（DeepSeek）出蓝图 → 强模型定稿。
如需控制字数，加 `--target-words 4000` 等。使用 `--simple` 回到原始单段式。

如果字幕已经有说话人，或只有单人内容，可以跳过说话人推断：

```bash
uv run podlator pipeline-douyin "episode.srt" \
  -o "抖音解说稿.md" \
  --skip-speakers
```

### 3. 分步调试口播稿

如果要检查中间产物，按下面三步跑：

```bash
# SRT -> Transcript JSON，纯解析，不调用 LLM
uv run podlator parse-srt "episode.srt" \
  -o "transcript.json" \
  --title "Episode Title"

# Transcript JSON -> 带 speaker 的 Transcript JSON，调用 LLM
uv run podlator assign-speakers "transcript.json" \
  -o "transcript.speakers.json"

# Transcript JSON -> 中文口播稿，默认两段式，约 6000 字
uv run podlator douyin-script "transcript.speakers.json" \
  -o "抖音解说稿.md" \
  --title "Episode Title"

# 用本机 claude -p 强模型定稿（需已登录 Claude Code 会员）
uv run podlator douyin-script "transcript.speakers.json" \
  -o "抖音解说稿.md" \
  --title "Episode Title" \
  --finalize-provider claude_cli

# 单段式（旧行为，一次 LLM 调用）
uv run podlator douyin-script "transcript.speakers.json" \
  -o "抖音解说稿.md" \
  --title "Episode Title" \
  --simple
```

`douyin-script` 的输出不是逐字翻译，也不是简报，而是适合中文播客/短视频口播的解说稿：钩子开场、人物背景、按主题重组、术语白话化、补充必要外部背景。

支持的 provider：`deepseek` / `claude`（第三方 API）/ `claude_cli`（本机 Claude Code）/ `codex_cli`（本机 Codex CLI）。

Codex CLI 非交互式调用、联网搜索和 Podlator 接入方式见
[`docs/CODEX_CLI_NON_INTERACTIVE.md`](docs/CODEX_CLI_NON_INTERACTIVE.md)。

### 4. 整理播客发布文案

目前标题、简介、开场白没有单独的 Podlator 命令。当前做法是根据口播稿和原始节目手动整理，例如第 08 期：

```text
project/08How Microsoft thinks about AGI/抖音剪辑版/播客meta.md
project/08How Microsoft thinks about AGI/抖音剪辑版/开场文案.md
```

通常包含：

- 播客标题
- 播客简介
- 来源说明
- 开场文案

### 5. TTS：开场白和正片分开生成

Podlator 当前不内置 TTS。中文稿件转语音统一调用外部 `speech-transcriber` 项目的 `synthesize` CLI。

外部项目默认路径：

```text
/Users/mac/Project_Personal/speech-transcriber
```

推荐使用 `uv run --project`，避免误读 Podlator 的 `.env`：

```bash
# 开场白 TTS
uv run --project /Users/mac/Project_Personal/speech-transcriber \
  speech-transcriber synthesize \
  --text-file "/Users/mac/Project_Personal/podlator/project/08How Microsoft thinks about AGI/抖音剪辑版/开场文案.md" \
  --output-file "/Users/mac/Project_Personal/podlator/project/08How Microsoft thinks about AGI/抖音剪辑版/开场文案.mp3" \
  --speech-rate 8 \
  --json

# 正片口播稿 TTS
uv run --project /Users/mac/Project_Personal/speech-transcriber \
  speech-transcriber synthesize \
  --text-file "/Users/mac/Project_Personal/podlator/project/08How Microsoft thinks about AGI/抖音剪辑版/抖音解说稿_Microsoft_AGI.md" \
  --output-file "/Users/mac/Project_Personal/podlator/project/08How Microsoft thinks about AGI/抖音剪辑版/抖音解说稿_Microsoft_AGI.mp3" \
  --speech-rate 8 \
  --json
```

分开生成的原因是开场白和正片常常需要不同的语气、节奏或版本。

### 6. 拼接最终音频

音频拼接目前手动完成。第 08 期的最终产物示例：

```text
project/08How Microsoft thinks about AGI/抖音剪辑版/播客完整版_Microsoft_AGI_含开场.mp3
```

可以用 `ffmpeg` 拼接；如果两段 MP3 编码参数一致，可以直接 concat，否则需要重新编码。

## 仍然保留的功能

这些功能仍在 CLI 中存在，适合调试、复用或跑早期的中文简报工作流。

### 从 URL 下载音频

```bash
uv run podlator download "https://www.youtube.com/watch?v=XXXXX" \
  -o "episode.mp3" \
  --metadata "meta.json"
```

输出音频文件和可选的 metadata JSON。依赖 `yt-dlp`。

### 音频转 Transcript JSON

```bash
uv run podlator transcribe "episode.mp3" \
  -o "transcript.json" \
  --provider tencent_cloud
```

这一步通过外部 `speech-transcriber` CLI 完成 ASR。Podlator 本身不直接调用腾讯云 ASR 或其他 ASR SDK。

### 章节切分

```bash
uv run podlator split "transcript.speakers.json" \
  -o "chapters.json"
```

输出 `Chapters JSON`，只包含章节结构：`title/start/end/segment_indices`。它不翻译、不摘要。

### 中文摘要或全文翻译

```bash
# 精简摘要
uv run podlator render "transcript.speakers.json" \
  --chapters "chapters.json" \
  --mode summary \
  -o "summary.md"

# 全文翻译
uv run podlator render "transcript.speakers.json" \
  --chapters "chapters.json" \
  --mode full \
  -o "full-translation.md"
```

`summary` 适合快速浏览，`full` 适合存档。

### 润色简报

```bash
uv run podlator polish "summary.md" \
  -o "brief.md" \
  --title "Episode Title"
```

这条路线是早期“英文播客 -> 中文简报”的工作流，和当前的口播稿生成路线不同。

### 一键 URL 到简报

```bash
uv run podlator run "https://www.youtube.com/watch?v=XXXXX"
```

这是保留的 LangGraph pipeline，会按节点执行：

```text
fetch_metadata -> download_audio -> transcribe -> diarize? -> chapter_split
  -> summarize_chapters -> polish_final -> export_markdown
```

中间产物归档在：

```text
data/artifacts/{task_id}/
```

最终简报在：

```text
data/briefs/{task_id}/
```

## CLI 命令概览

| 命令 | 输入 | 输出 | 说明 |
|---|---|---|---|
| `pipeline-douyin` | `.srt` | `.md` 口播稿 | 当前最常用：字幕到中文口播稿 |
| `douyin-script` | `transcript.json` | `.md` 口播稿 | 两段式，支持 claude_cli/codex_cli |
| `parse-srt` | `.srt` | `transcript.json` | 纯解析，不调 LLM |
| `assign-speakers` | `transcript.json` | `transcript.json` | LLM 推断说话人 |
| `download` | URL | 音频 + metadata | 下载音频 |
| `transcribe` | 音频 | `transcript.json` | 调外部 ASR CLI |
| `split` | `transcript.json` | `chapters.json` | 章节切分 |
| `render` | transcript + chapters | `.md` | 中文摘要或全文翻译 |
| `polish` | `.md` | `.md` | 简报润色 |
| `eval` | `.md` | `.review.json` | 程序 lint + LLM judge 自动评分 |
| `run` | URL | `.md` 简报 | 早期一键 LangGraph 简报 pipeline |

查看完整参数：

```bash
uv run podlator --help
uv run podlator pipeline-douyin --help
uv run podlator douyin-script --help
```

## 文件格式

Step CLI 之间主要通过两个 JSON 格式衔接。

### Transcript JSON

```json
{
  "schema_version": 1,
  "source": {
    "audio_path": "episode.mp3",
    "source_url": "https://www.youtube.com/watch?v=XXXXX",
    "title": "Episode Title",
    "duration_seconds": 1234.5
  },
  "provider": {
    "name": "srt",
    "cost_usd": 0.0
  },
  "text": "Full transcript text...",
  "segments": [
    {
      "index": 0,
      "start": 0.0,
      "end": 5.25,
      "speaker": "HOST",
      "text": "Welcome to the show.",
      "confidence": null
    }
  ]
}
```

### Chapters JSON

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

## 安装和配置

前置要求：

- Python 3.12+
- Node.js 20+（只在跑 Web UI 时需要）
- `uv`
- `pnpm`（只在跑 Web UI 时需要）
- `ffmpeg`
- 外部 `speech-transcriber` 项目

安装：

```bash
uv sync

cd web
pnpm install
cd ..
```

配置：

```bash
cp .env.example .env
```

常用配置项：

```text
DEEPSEEK_API_KEY=
CLAUDE_API_KEY=
LLM_PROVIDER_SUMMARIZE=deepseek
LLM_PROVIDER_POLISH=claude          # 也可设为 claude_cli / codex_cli
SPEECH_TRANSCRIBER_PROJECT_DIR=/Users/mac/Project_Personal/speech-transcriber
SPEECH_TRANSCRIBER_PROVIDER=tencent_cloud

# 如果用 claude_cli / codex_cli 定稿（可选，不设则用上面的 POLISH）
# CLI_TOOL_BACKEND=claude
# CLI_TOOL_CLAUDE_MODEL=claude-sonnet-4-6
# CLI_TOOL_CODEX_MODEL=gpt-5
# CLI_TOOL_TIMEOUT_S=600
```

TTS 相关配置在外部 `speech-transcriber/.env` 中维护，不在 Podlator 的 `.env` 里维护。

## Web UI

Web UI 是早期 MVP 能力，主要用于提交 URL、查看任务、看日志和简报。

```bash
# 后端
uv run uvicorn podlator.api.main:app --reload --port 8000

# 前端
cd web
pnpm dev
```

访问：

```text
http://localhost:5173
```

## 项目结构

```text
podlator/
├── src/podlator/
│   ├── cli.py                   # Typer CLI 入口
│   ├── config.py                # 配置加载
│   ├── steps/                   # 文件转换型业务能力
│   ├── prompts/                 # Prompt 模板
│   ├── graph/                   # LangGraph 简报 pipeline
│   ├── providers/               # LLM / STT / Downloader 适配器
│   ├── api/                     # FastAPI + WebSocket
│   └── storage/                 # SQLite + 路径管理
├── project/                     # 手动项目产物：字幕、口播稿、meta、音频
├── data/                        # 运行时数据和 artifacts
├── docs/                        # 设计文档和历史任务文档
├── tests/                       # 单元、集成、smoke 测试
├── web/                         # Vite + React 前端
├── README.md
├── CLAUDE.md                    # AI 协作指南
├── CHANGELOG.md
└── pyproject.toml
```

## 开发约定

- 项目协作和代码规范以 `CLAUDE.md` 为准。
- 新功能需要补测试和日志。
- 改变使用方式时更新 `README.md`。
- 改变 AI 协作约定或项目结构时更新 `CLAUDE.md`。
- 重要变更记录到 `CHANGELOG.md`。

## 许可

私人项目，未开源。
