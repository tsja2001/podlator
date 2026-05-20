# 路线图

> 每个 Milestone 是一个可交付的增量。**严格顺序执行，不跳跃。**

---

## M0 — 项目骨架

> 详细执行步骤见 `docs/tasks/M0-execution.md`。

**目标**: 搭建完整的项目骨架。所有代码能编译、能测试、能启动，但不做任何真实工作。

**交付物**:
- pyproject.toml + uv sync 可用
- 完整的 Python 包结构（src/podlator/ 下所有模块）
- PodlatorState 定义 + 8 个占位节点 + Graph 可编译
- Provider 接口定义（STT / LLM / Downloader）
- SQLite TaskStore（CRUD 可用）
- FastAPI 应用（路由注册，返回 501 占位）
- Typer CLI（`podlator --help` 可用）
- structlog 配置（控制台 + JSON 文件输出）
- pytest 基础设施（conftest + 每个模块至少 1 个测试）
- 前端 Vite + React 骨架（空白页面可访问）
- .gitignore + 首次提交

**验收标准**:
- [ ] `uv sync` 成功
- [ ] `uv run pytest` 全绿（至少 20 个测试）
- [ ] `uv run ruff check .` 无错误
- [ ] `uv run ruff format --check .` 通过
- [ ] `uv run mypy src/` 无错误
- [ ] `uv run podlator --help` 输出帮助信息
- [ ] `uv run podlator version` 输出版本号
- [ ] `uv run uvicorn podlator.api.main:app` 能启动，`/api/health` 返回 200
- [ ] `cd web && pnpm dev` 能跑，浏览器可访问
- [ ] 测试覆盖率 >= 70%
- [ ] Git 有干净的首次提交

**预计耗时**: AI 执行约 1-2 小时（含验证）

---

## M1 — 核心 Pipeline 跑通

**目标**: 实现所有 Provider + 节点逻辑，CLI 投喂一个 URL 能产出完整的中文简报 Markdown。

**前置条件**:
- M0 完成
- Deepgram / DeepSeek / Anthropic API Key 已配置
- 准备好 1 个测试用 YouTube URL（5-10 分钟英文播客）

**交付物**:
- `YtDlpDownloader` 实现（fetch_metadata + download）
- `DeepgramProvider` 实现（transcribe，含说话人分离）
- `DeepSeekProvider` 实现（chapter_split + summarize_chapters）
- `ClaudeProvider` 实现（polish_final）
- 8 个节点全部真实实现
- Prompt 模板文件（`src/podlator/prompts/*.md`）
- CLI `podlator run <url>` 端到端可用
- 每个 Provider 的 unit 测试（mock HTTP）
- 每个节点的 unit 测试（mock Provider）
- 1 个 integration 测试（mock 所有外部 API，跑完整 pipeline）
- 3 个 smoke 测试（真实 API 调用，`PODLATOR_RUN_SMOKE=1` 开启）

**验收标准**:
- [ ] `uv run podlator run "<测试URL>"` 产出 Markdown 文件
- [ ] 产出的简报包含：标题、引言、至少 2 个章节摘要、结论
- [ ] 简报是通顺的中文
- [ ] 单期 10 分钟播客的总 API 费用 < ¥2
- [ ] `uv run pytest` 全绿
- [ ] 覆盖率 >= 75%（新增代码 >= 80%）
- [ ] 所有 Provider 都测了至少 1 个失败场景

**预计耗时**: AI 执行约 3-5 小时 + 人工 review prompt 质量

---

## M2 — Web UI MVP

**目标**: 提供 Web 界面，可提交 URL、查看队列、实时观看日志、阅读简报。

**前置条件**:
- M1 完成
- 前端开发环境就绪（已有 M0 骨架）

**交付物**:
- FastAPI 路由全部实现（CRUD + 启动 pipeline）
- WebSocket 日志推送（structlog → WS → 前端）
- 4 个前端页面：Submit / Queue / TaskDetail / BriefViewer
- 前端组件：TaskCard、LogViewer、BriefRenderer
- TanStack Query 数据层 + WebSocket hook
- 后端 integration 测试（httpx.AsyncClient）
- 前端 vitest 组件测试

**验收标准**:
- [ ] 浏览器提交 URL → 后端开始处理
- [ ] TaskDetail 页面实时显示日志
- [ ] 处理完成后 BriefViewer 可读简报
- [ ] Queue 页面列表可筛选状态
- [ ] API 错误有友好提示（非白屏）
- [ ] `pnpm build` 无错误

---

## M3 — 质量提升

**目标**: 优化 Prompt、改善输出质量、添加说话人命名和术语一致性。

**交付物**:
- Prompt 工程迭代（至少 3 轮人工评估）
- 说话人命名规则（从 "SPEAKER_0" 到实际名字）
- 术语表功能（常见播客中的人名、产品名、缩写）
- 输出格式模板化（简报格式可配置）
- Prompt 评估脚本（`tests/prompts/`）

---

## M4 — 本地 STT 兜底

**目标**: 实现 mlx-whisper 本地转写 + pyannote 说话人分离，作为 Deepgram 的 fallback。

**交付物**:
- `MLXWhisperProvider` 实现
- pyannote.audio 集成
- `diarize` 节点真实实现
- Deepgram 失败时自动 fallback 到本地
- 本地 vs 云的质量对比报告

---

## M5 — 自动化与分发

**目标**: RSS 订阅自动抓取新集、定时任务、输出 RSS feed。

**交付物**:
- RSS 订阅管理（增删改查）
- 定时轮询新集（可配置间隔）
- 自动触发 pipeline
- 输出为 RSS feed（简报作为 feed item）
- Web UI 订阅管理页面

---

## M6 — TTS 中文播报

**目标**: 将中文简报转为音频，生成可听的中文播报版本。

**交付物**:
- TTS Provider 接口
- 火山引擎 TTS 实现（云）
- IndexTTS 实现（本地备选）
- 音频后处理（拼接、背景音乐）
- Web UI 音频播放器
