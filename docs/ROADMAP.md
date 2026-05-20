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

**子任务**:
- `M2.1-websocket.md` — WebSocket 实时日志推送（后端 structlog → WS → 前端）
- `M2.2-frontend.md` — 4 个前端页面 + 组件 + TanStack Query 数据层

**前置条件**:
- M1 完成
- 前端开发环境就绪（已有 M0 骨架）

**用户需准备**:
- 无额外准备（M1 的 API Key 继续使用）
- 建议有一个已完成的任务记录（M1 smoke 测试会产生）

**交付物**:
- WebSocket 日志推送（structlog → WS → 前端）
  - 后端：structlog 自定义 processor，实时写入 WS 连接
  - 前端：`useTaskLogs(taskId)` hook
- 4 个前端页面真实实现：
  - `SubmitPage` — URL 输入框 + 提交按钮 + 提交反馈
  - `QueuePage` — 任务卡片列表 + 状态筛选 + 自动轮询刷新
  - `TaskDetailPage` — 实时日志滚动 + 节点进度条 + 基本信息
  - `BriefViewerPage` — Markdown 渲染 + 复制/下载
- 前端组件：TaskCard、LogViewer、BriefRenderer、NodeProgressBar
- TanStack Query 数据层（useQuery / useMutation / WebSocket hook）
- shadcn/ui 组件安装
- 前端 vitest 组件测试

**验收标准**:
- [ ] 浏览器提交 URL → 后端开始处理（API 调用成功、队列更新）
- [ ] TaskDetail 页面实时显示 structlog 日志（WebSocket 连通）
- [ ] 处理完成后 BriefViewer 渲染 Markdown 简报
- [ ] Queue 页面列表可按状态筛选、自动刷新
- [ ] API 错误有 toast 提示（非白屏）
- [ ] `pnpm build` 无错误
- [ ] vitest 测试通过

**预计耗时**: AI 执行约 3-4 小时

---

## M3 — 质量提升

**目标**: 优化 Prompt、改善输出质量、添加说话人命名和术语一致性。

**子任务**:
- `M3.1-prompt-iteration.md` — Prompt 工程迭代（3 轮评估）
- `M3.2-speaker-terms.md` — 说话人命名 + 术语表

**前置条件**:
- M1 完成（能跑 pipeline 产出简报）
- 至少跑过 3 期不同播客（积累样本）

**用户需准备**:
- 3-5 个已跑完的简报（评估 prompt 质量用）
- 至少 1 个多人对话播客的 URL（测试说话人命名）
- 如果有常听的播客，提供术语表（人名、产品名、缩写对照）

**交付物**:
- Prompt 评估脚本（`tests/prompts/eval_quality.py`）
  - 自动检查：章节数合理、摘要长度、中文比例、关键词覆盖
  - 人工检查清单：流畅度、信息完整度、专有名词准确度
- 至少 3 版 Prompt（在 git 中可追溯）
- 说话人命名逻辑：
  - 从转录上下文推断说话人身份（"As the host mentioned..."）
  - 配置文件指定播客固定角色（如 `hosts.yaml`）
- 术语表功能：
  - `src/podlator/glossary.py` — YAML 术语表加载
  - `data/glossary.yaml` — 用户可编辑的术语对照表
  - Prompt 中注入术语表上下文
- 输出格式可配置（简报模板选择）

**验收标准**:
- [ ] 用 3 期真实播客评估，简报质量评分 ≥ 7/10（用户主观评分）
- [ ] 多人对话播客的说话人命名正确率 ≥ 80%
- [ ] 术语表中的词在简报中使用正确
- [ ] Prompt 评估脚本可自动运行
- [ ] 覆盖率 ≥ 75%

**预计耗时**: AI 执行约 2-3 小时 + 用户评估 1-2 小时

---

## M4 — 本地 STT 兜底

**目标**: 实现 mlx-whisper 本地转写 + pyannote 说话人分离，作为 Deepgram 的 fallback。

**子任务**:
- `M4.1-mlx-whisper.md` — MLXWhisperProvider 实现
- `M4.2-pyannote.md` — pyannote diarize 节点实现
- `M4.3-fallback.md` — 自动降级逻辑

**前置条件**:
- M1 完成
- Apple Silicon Mac（mlx-whisper 只支持 Apple Silicon）

**用户需准备**:
- **Hugging Face 账号 + token**（pyannote 模型需要通过 HF 下载）
  1. 注册 https://huggingface.co/
  2. 访问 https://huggingface.co/pyannote/speaker-diarization-3.1 → 同意许可
  3. 创建 Access Token：Settings → Access Tokens → New token
  4. 填入 `.env` 的 `HF_TOKEN=`
- **磁盘空间**：mlx-whisper 模型约 1.5GB，pyannote 约 200MB
- **耐心**：首次运行会下载模型，可能要 10-30 分钟

**交付物**:
- `MLXWhisperProvider` 实现
  - 使用 `mlx_whisper` 包本地转写
  - 支持 large-v3 模型（质量最佳）
- `pyannote.audio` 集成
  - `diarize` 节点真实实现（给 segments 添加 speaker 标签）
  - 使用 `pyannote/speaker-diarization-3.1` pipeline
- 自动降级逻辑：
  - Deepgram 失败（网络/额度耗尽）→ 自动切换 mlx-whisper
  - 日志记录 `fallback_triggered` 事件
  - 在 `transcribe` 节点内用 `tenacity` retry + fallback
- 新增配置项：`HF_TOKEN`、`MLX_WHISPER_MODEL`
- 质量对比报告（同一段音频，Deepgram vs mlx-whisper 的差异）

**验收标准**:
- [ ] `STT_PROVIDER=mlx_whisper` 时能本地转写
- [ ] Deepgram mock 失败 → 自动 fallback 到本地 → pipeline 完成
- [ ] 本地转写质量可接受（WER < 15%）
- [ ] diarize 节点正确标注说话人
- [ ] 覆盖率 ≥ 75%

**预计耗时**: AI 执行约 3-4 小时（含模型下载等待）

---

## M5 — 自动化与分发

**目标**: RSS 订阅自动抓取新集、定时任务、输出 RSS feed。

**子任务**:
- `M5.1-rss-input.md` — RSS 订阅解析 + 新集检测
- `M5.2-scheduler.md` — 定时轮询 + 自动触发 pipeline
- `M5.3-rss-output.md` — 生成 RSS feed（简报作为 feed item）

**前置条件**:
- M2 完成（Web UI 可用）
- M1 pipeline 稳定运行

**用户需准备**:
- 2-3 个常听的英文播客 RSS Feed URL
  - 获取方式：在 Apple Podcasts 或 Pocket Casts 中找到播客 → 复制 RSS Feed URL
  - 或者用 https://getrssfeed.com/ 从播客名搜索
  - 例如：Lex Fridman、All-In、Huberman Lab 等
- 确认播客更新频率（用于设定轮询间隔）

**交付物**:
- RSS 解析器（`feedparser` 库）
- 订阅管理（DB 表 + CRUD API + Web UI 页面）
- 新集检测逻辑（对比已处理的 episode GUID）
- `APScheduler` 或 `asyncio` 定时任务
- RSS Feed 输出生成器（`rfeed` 或手动 XML）
- Web UI 订阅管理页面

**验收标准**:
- [ ] 添加 RSS 订阅后，系统自动检测并处理新集
- [ ] 定时轮询间隔可配置
- [ ] 已处理的集不会重复处理
- [ ] `/feed.xml` 输出有效的 RSS Feed
- [ ] Web UI 可增删查改订阅

**预计耗时**: AI 执行约 4-5 小时

---

## M6 — TTS 中文播报

**目标**: 将中文简报转为音频，生成可听的中文播报版本。

**子任务**:
- `M6.1-tts-provider.md` — TTS Provider 接口 + 火山引擎实现
- `M6.2-audio-pipeline.md` — 音频拼接 + 后处理
- `M6.3-player.md` — Web UI 音频播放器

**前置条件**:
- M1 完成（有简报 Markdown 可用）

**用户需准备**:
- **火山引擎账号**（推荐）：
  1. 注册 https://console.volcengine.com/
  2. 开通"语音技术" → "语音合成"
  3. 获取 Access Key + Secret Key
  4. 选择音色（推荐：中文女声 zh_female_shuangkuai）
- **或 IndexTTS**（本地备选）：
  - GitHub: https://github.com/indexteam/index-tts
  - 需要 GPU 或足够的 CPU 算力
  - 模型约 2GB 磁盘空间
- **ffmpeg 已安装**（音频拼接需要）

**交付物**:
- TTS Provider 接口（`src/podlator/providers/tts/base.py`）
- 火山引擎 TTS 实现（云）
- IndexTTS 实现（本地备选）
- 音频后处理管道：分段合成 → 拼接 → 标准化音量
- 新增 Graph 节点：`generate_audio`（在 export_markdown 之后）
- Web UI 音频播放器组件
- 配置项：TTS_PROVIDER、语速、音色等

**验收标准**:
- [ ] 简报 Markdown → 中文音频文件
- [ ] 音频质量可接受（无明显卡顿或乱码）
- [ ] 单期 10 分钟播客的 TTS 费用 < ¥0.5
- [ ] Web UI 可在线播放
- [ ] 覆盖率 ≥ 75%

**预计耗时**: AI 执行约 3-4 小时

---

## 里程碑依赖关系

```
M0 (骨架) ──→ M1 (核心 pipeline) ──→ M2 (Web UI)
                 │                       │
                 ├──→ M3 (质量提升) ←────┘
                 │
                 ├──→ M4 (本地 STT)
                 │
                 ├──→ M5 (自动化) ← M2
                 │
                 └──→ M6 (TTS)
```

- M2 依赖 M1（需要真实 pipeline 输出）
- M3 可在 M1 或 M2 之后任何时间做（独立于 UI）
- M4 独立于 M2/M3，随时可做
- M5 需要 M2（Web UI 管理页面）
- M6 独立于其他里程碑，只需 M1
