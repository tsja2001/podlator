# Changelog

所有重大变更记录在此文件。格式参考 [Keep a Changelog](https://keepachangelog.com/)。

## [Unreleased]

### Added
- README 和 CLAUDE.md 新增手动 TTS 工作流说明：中文稿件转语音必须调用外部
  `speech-transcriber synthesize`（火山引擎 Seed TTS 2.0），并明确工作目录和路径映射约束。
- **抖音解说稿生成能力**：新增 `douyin-script` 和 `pipeline-douyin` CLI 命令。
  - `douyin-script`：Transcript JSON → 口语化中文解说稿 Markdown。
  - `pipeline-douyin`：SRT 字幕 → 解说稿全自动流水线（parse-srt → assign-speakers → douyin-script）。
- **说话人分离分片（sharding）**：`assign-speakers` 新增长 transcript 自动分片处理，含跨分片标签归一化和边界连续性保证。
- 新增 prompt 模板：`douyin_script.md`（抖音解说稿风格规范，v2 已优化）。
- 新增 step：`douyin_script.py`，注册到 Step Registry。
- 新增 SRT 测试 fixture：`tests/fixtures/sample_interview.srt`。
- **风格规范文档**：`docs/goal目标制定/风格规范-抖音解说稿prompt蓝图.md`（6 条核心转化规律）。
- **差距分析**：`docs/goal目标制定/差距分析-三篇产出vs黄金样本.md`（v1/v2 两轮评分）。
- **三个播客的抖音解说稿产出**（`project/*/抖音剪辑版/`）。

### Changed
- README 重写为以当前“英文 SRT 字幕 → 中文口播稿 → 外部 TTS → 拼接音频”工作流为主的简明说明，并保留旧的简报、全文翻译、URL 下载转写等 CLI 能力概览。
- CLAUDE.md 补充当前优先使用的 `pipeline-douyin` 播客生成工作流，并纠正 `transcribe` 节点当前依赖外部 `speech-transcriber` CLI 的说明。
- `assign-speakers` 重构：抽取 `_parse_llm_content`、`_shard_segments`、`_process_shard`、`_normalize_labels_across_shards`、`_merge_shard_results` 函数。
- 新增 `shard_size`、`shard_overlap` 参数。
- Step Registry 新增 `douyin_script` 条目。
- `douyin_script.md` prompt v2 优化：禁止 Markdown 标题/LLM 引导语、增加外部知识硬性要求（≥3 处）、增加人物介绍和现场感要求。

## [Unreleased]

### Added
- 文件转换型 Step CLI：`download`、`transcribe`、`parse-srt`、`assign-speakers`、`split`、`render`、`polish` 七个单步命令。
- SRT 字幕解析：`parse-srt subtitles.srt -o transcript.json`，纯解析不调 LLM。
- LLM 说话人推断：`assign-speakers transcript.json -o transcript.speakers.json`，以及 `parse-srt --assign-speakers` 快捷路径。
- `render --mode full` 支持按章节生成中文全文翻译。
- Step 文件格式层：`TranscriptDocument`、`ChapterDocument` 等 Pydantic 模型，JSON 读写层。
- Step Registry：为后续 Workflow YAML 配置化预留接口。
- M1.4 文件转换型 Step CLI + 可组合 LangGraph Workflow 方案文档。
- README 新增详细 CLI 步骤文档：每个命令的参数表、输入/输出文件说明、中间文件格式、典型工作流示例。
- 腾讯云 ASR 大模型版 STT Provider，使用 COS 临时上传音频并生成预签名 URL 提交录音文件识别任务。
- Tencent COS 音频暂存封装，支持上传、GET 预签名和识别后清理。

### Changed
- LangGraph node 改为复用 `steps` 层，CLI 和 graph 共享同一套业务能力。
- `transcribe` step 改为调用独立的 `speech-transcriber` CLI，不再在 Podlator 内直接维护腾讯云 ASR / COS 调用。
- 章节切分使用带时间戳的 transcript segments，避免模型猜测 start/end。
- 新增 `speech_transcriber_project_dir` 和 `speech_transcriber_provider` 配置项。
- 腾讯云 ASR/COS 单元测试和 gated smoke 测试。
- Pipeline artifacts 归档：每个任务在 `data/artifacts/{task_id}/` 下按 `01/02/...` 写入链接、元数据、音频副本、转写文本、章节、摘要、最终简报和节点日志，方便排查中间产物截断问题。
- M2 Web UI MVP 开发计划文档，覆盖后端 WebSocket 日志、任务执行、前端页面与测试验证。
- M1.3 CLI 集成 + 端到端测试
  - `podlator run` 真实 pipeline 执行（异步 LangGraph）
  - `podlator status` / `podlator list` 查询任务
  - API 后台 pipeline 执行（BackgroundTasks）
  - `POST /api/tasks/{id}/retry` 重试失败任务
  - `GET /api/tasks/{id}/brief` 获取简报 Markdown
  - 完整 pipeline 集成测试（mock 所有外部 API）
  - Smoke E2E 测试（真实 API，按需执行）
  - State 字段支持 LangGraph reducer（`total_cost_usd` 累加，`node_durations_ms` 合并）
- M1.2 全部 8 个节点实现 + Prompt 模板
- M1.1 Provider 实现（YtDlp / Deepgram / DeepSeek / Claude）
- 项目骨架搭建（M0）
- LangGraph 状态机
- Provider 接口定义（STT / LLM / Downloader）
- FastAPI + WebSocket 应用骨架
- Typer CLI 入口
- structlog 日志配置
- SQLite TaskStore
- pytest 测试基础设施
- Vite + React 前端骨架

### Changed
- 本地 `.env` 增加 `CLAUDE_MODEL` 配置，并补充测试确保 Claude provider 使用配置中的模型名。
- `polish_final` 节点在 Claude 可重试失败时自动降级到 DeepSeek，避免最后润色阶段网络超时导致整条 pipeline 失败。
- `PodlatorState` 中 `total_cost_usd` 和 `node_durations_ms` 使用 `Annotated` + reducer 实现累加语义
- 各节点返回 `total_cost_usd` 以支持费用累积
- CLI 命令从占位实现替换为真实逻辑
