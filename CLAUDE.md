# CLAUDE.md

> 本文件是给 AI IDE 助手（Claude Code / Cursor / Windsurf 等）的项目协作指南。
> 在开始任何工作前，**先读完本文件 + README.md**，然后查看 `docs/ROADMAP.md` 确认当前阶段。
>
> **本项目对测试和日志有强制要求，详见第 7、9、13 章。任何违反 DoD（第 13 章）的提交都视为未完成。**

---

## 1. 项目身份

**Podlator** 是一个自用的英文播客 / YouTube 视频播客 → 中文简报自动化工具。

- **架构核心**：基于 **LangGraph (Python)** 的状态机 pipeline
- **后端**：FastAPI + WebSocket
- **前端**：Vite + React + TanStack Query + shadcn/ui
- **存储**：SQLite + 本地文件系统
- **运行环境**：macOS（Apple Silicon），单机自用

详细背景见 `README.md`。

---

## 2. 用户画像与协作偏好

用户是一位 **前端 / Node.js 背景** 的开发者，正在系统性学习 Python AI 生态，**对测试工程是新手**。

### 协作偏好

- **代码风格**：多写注释，特别是 Python 的异步、类型注解、装饰器等 JS 不常见的特性
- **必要时类比 JS 生态**："这相当于 npm 的 X" / "类似 Express 的 middleware" / "pytest fixture 相当于 vitest 的 beforeEach + 依赖注入"
- **解释风格**：简洁 prose + 必要 bullet，**避免过度铺陈**
- **学习模式**：遇到设计选择时**简要解释为什么这样选**（一两句话），不需要长篇大论
- **三大架构特性**重点维护：**可观察性、可测试性、可演进性**
- **回答语言**：中文
- **测试是非可选项**：用户重视代码质量胜过开发速度，**绝不允许跳过测试**

### 何时停下来问用户

- 设计上有多个合理选择且影响深远
- 引入新的重量级依赖
- 需要 API key / 外部账号
- Prompt 模板的具体措辞（产品决策）
- 任何破坏现有测试的改动

### 何时不要问，直接做

- 单纯的代码风格、命名、文件组织
- 已经在 README / CLAUDE.md / ROADMAP 中明确的约定
- 重构以提升可测试性、可观察性
- 添加测试用例 / 补充日志
- 写注释 / 文档

---

## 3. 工作流程（每次开发新功能必须遵循）

### 标准流程

每次完成一项需求（无论大小），**严格按以下顺序执行**：

1. **理解需求**：确认要改的是哪个节点 / 模块，影响哪些文件，**写一句话总结你的理解**
2. **规划测试**：列出本次改动需要新增 / 更新的测试用例清单（参考第 9 章测试矩阵）
3. **先写或更新测试**（**TDD 优先**；如果是探索性代码，至少与实现同步写）
4. **实现功能**
5. **补充日志**：按第 7 章规范，关键路径加日志
6. **执行 DoD 检查清单**（第 13 章）—— **任何一项不通过禁止宣告完成**
7. **更新文档**：
   - 必改 `CHANGELOG.md`（按时间倒序追加）
   - 如改动了使用方式 → 更新 `README.md`
   - 如改动了架构 / 约定 → 更新 `CLAUDE.md`
   - 如新增节点 → 更新 `docs/ARCHITECTURE.md` 中的节点列表
8. **提交**：使用约定式提交格式

### 提交信息格式（Conventional Commits）

```
feat(graph): 添加 diarize 节点
fix(stt): Deepgram 超时重试逻辑
docs: 更新 ROADMAP M2 验收标准
test(summarize): 添加章节切分边界用例
refactor(providers): 抽象 LLM 接口
chore: 升级 langgraph 到 0.2.5
```

scope 对应模块名：`graph` / `stt` / `llm` / `api` / `web` / `storage` / `test` / `docs` 等。

---

## 4. 架构核心：LangGraph 状态机

### 关键文件

- `src/podlator/graph/state.py` — **PodlatorState** 定义
- `src/podlator/graph/builder.py` — Graph 组装与编译
- `src/podlator/graph/nodes/` — 节点实现（每个节点一个文件）
- `src/podlator/graph/nodes/_base.py` — 节点装饰器和工具

### 节点设计原则

1. **每个节点是异步纯函数**：`async def run(state: PodlatorState) -> dict`
2. **节点不直接调用彼此**：所有数据通过 state 传递
3. **节点之间不假设执行顺序**：除非 builder 中明确连接
4. **失败抛出 `NodeError`**：由 graph 决定重试 / 跳过 / 终止
5. **使用 `@node("name")` 装饰器**：自动注入计时、日志、异常包装
6. **节点返回 patch（dict），不要返回整个 state**：LangGraph 会自动合并
7. **节点必须可单独测试**：所有外部依赖通过依赖注入或参数传入

### 节点代码模板

```python
"""节点：<一句话描述>。

实现策略：
- <要点 1>
- <要点 2>
"""
from __future__ import annotations

from typing import Any

from podlator.graph.nodes._base import node, node_logger
from podlator.graph.state import PodlatorState


@node("node_name")
async def run(state: PodlatorState) -> dict[str, Any]:
    log = node_logger(state, "node_name")
    log.info("doing_something", relevant_field=state.get("xxx"))

    # ... 主要逻辑 ...

    return {
        "some_field": result,
        # 装饰器会自动注入 current_node 和 node_durations_ms
    }
```

### 当前节点列表

| 节点 | 职责 | 主要依赖 |
|---|---|---|
| `fetch_metadata` | 抓取标题、时长、发布时间 | yt-dlp / feedparser |
| `download_audio` | 下载音频文件 | yt-dlp |
| `transcribe` | STT 转写 | Deepgram (主) / mlx-whisper (备) |
| `diarize` | 说话人分离（如 STT 未自带）| pyannote.audio |
| `chapter_split` | 按主题切分章节 | DeepSeek V4-Flash |
| `summarize_chapters` | 章节翻译精简（并发）| DeepSeek V4-Flash |
| `polish_final` | 全局润色 + 引言/结论 | Claude Opus 4.7（第三方 OpenAI 兼容 API）|
| `export_markdown` | 导出 Markdown 文件 | — |

---

## 5. Provider 抽象层

### 设计目标

用户要的"混合策略"（STT 切 Deepgram / mlx-whisper，LLM 切 DeepSeek / Claude）通过**接口抽象**实现，**切换 provider = 改配置而非改代码**。

### 接口位置

- `src/podlator/providers/stt/base.py` — `STTProvider` 接口
- `src/podlator/providers/llm/base.py` — `LLMProvider` 接口
- `src/podlator/providers/downloader/base.py` — `Downloader` 接口

### 实现新 Provider 的步骤

1. 在对应目录新建 `<vendor>.py`（如 `deepgram.py`、`mlx_whisper.py`）
2. 继承基类，实现抽象方法
3. 在 `base.py` 的工厂方法（`get_stt_provider` 等）中注册
4. 在 `.env.example` 添加相关环境变量
5. 在 `tests/unit/providers/` 添加测试（用 mock，不要打真实 API）
6. **添加一个 smoke 测试**（在 `tests/smoke/`）用于偶尔验证真实 API
7. 更新 `README.md` 技术栈表

---

## 6. 代码规范

### Python

- **严格类型注解**（mypy strict 模式开启）
- **优先 pydantic 模型**而不是裸 dict（除非是 LangGraph state patch）
- **异步函数优先**（FastAPI + LangGraph 都是异步生态）
- **使用 `from __future__ import annotations`**（所有新文件）
- **导入顺序**：标准库 / 第三方 / 本地（用 ruff 自动整理）
- **文件顶部一行 docstring**：说明本模块职责

### TypeScript / React

- **函数组件 + hooks**
- **TanStack Query** 处理服务端状态（不要用 useEffect 拉数据）
- **shadcn/ui 组件优先**，需要时复制粘贴到 `web/src/components/ui/`
- **WebSocket 实时数据**走专门的 hook（`useTaskLogs`、`useTaskStatus`）

### 通用

- **避免缩写命名**：`task_id` 不要写 `tid`
- **错误信息要可操作**：告诉用户**怎么修**，不只是**哪里错了**

---

## 7. 日志规范（强制要求）

> 完整可观察性指南见 `docs/OBSERVABILITY.md`。本章是给 AI 的硬约束。

### 7.1 获取 logger

```python
from podlator.logging import get_logger

logger = get_logger(__name__)
```

### 7.2 节点中的标准用法

```python
@node("my_node")
async def run(state: PodlatorState) -> dict:
    log = node_logger(state, "my_node")   # 自动带 task_id + node
    log.info("node_started", input_size=len(state.get("xxx", "")))

    try:
        result = await some_api_call()
        log.info(
            "api_call_completed",
            provider="deepgram",
            duration_ms=123,
            tokens_in=456,
            tokens_out=789,
            cost_usd=0.01,
        )
        return {"result": result}
    except SomeAPIError as e:
        log.error(
            "api_call_failed",
            provider="deepgram",
            error_type=type(e).__name__,
            error_msg=str(e),
            retryable=True,
            exc_info=True,
        )
        raise NodeError("my_node", str(e), retryable=True) from e
```

### 7.3 必填字段表（按场景）

| 场景 | 必带字段 |
|---|---|
| **任意日志** | `task_id`（节点装饰器自动注入）、自动 `timestamp` |
| **节点进入** | `event="node_started"` |
| **节点完成** | `event="node_completed"`、`duration_ms`、`produced=[字段名列表]` |
| **节点失败** | `event="node_failed"`、`error_type`、`error_msg`、`retryable`、`exc_info=True` |
| **外部 API 调用** | `provider`、`endpoint`（或操作名）、`status_code`、`duration_ms` |
| **LLM 调用** | 加 `model`、`tokens_in`、`tokens_out`、`cost_usd` |
| **STT 调用** | 加 `audio_duration_seconds`、`cost_usd` |
| **文件操作** | `path`（绝对路径或相对项目根）、`size_bytes`（写文件时） |
| **重试** | `event="retry_attempt"`、`attempt`、`max_attempts`、`reason` |
| **降级** | `event="fallback_triggered"`、`from_provider`、`to_provider`、`reason` |

### 7.4 日志级别使用规则

- `DEBUG` — 详细中间状态（如 prompt 完整内容、HTTP raw response）。**生产关闭**
- `INFO` — 关键流程节点（节点开始/结束、API 调用完成）。**默认级别**
- `WARNING` — 降级行为（fallback、重试、跳过非关键步骤）
- `ERROR` — 失败但 pipeline 可继续（如某章节摘要失败，其他章节继续）
- `CRITICAL` — pipeline 必须中止（如配置缺失、磁盘满）

### 7.5 强制要求

**每个节点必须**：
- 开头 `log.info("node_started", ...)`
- 结尾 `log.info("node_completed", duration_ms=..., produced=[...])`（装饰器会自动加，节点内部可不写）

**每个外部 API 调用必须**：
- 调用前 `log.debug("api_request", endpoint=..., payload_summary=...)`
- 成功后 `log.info("api_call_completed", ...)`，**必带成本字段**
- 失败时 `log.error("api_call_failed", ...)`，**必带 `exc_info=True`**

**任何 `try/except` 必须 log**：
- **绝不允许静默吞异常**（`except: pass` 是禁止的，除非有明确注释说明为什么安全）
- 即使是预期内的异常（如某章节摘要失败），也必须 `log.warning(...)`

**绝对禁止**：
- ❌ `print(...)` —— 一律走 structlog
- ❌ `logger.info(f"Doing thing for {task_id}")` —— 用 kwargs 而不是 f-string
- ❌ 在循环中 log 每个迭代 —— 改为批量 log 总结
- ❌ log 中包含完整 API key 或敏感信息（即使在 DEBUG 级别）
- ❌ 把异常 catch 后只 print 不抛 —— 要么 log + raise，要么 log.warning 后明确说明继续的原因

### 7.6 输出去向

structlog 同时输出到：
1. **控制台**（pretty 彩色，便于开发期查看）
2. **JSON 文件**（`data/logs/podlator.log`，便于 Web UI 解析、问题排查）
3. **WebSocket**（实时推送给 Web UI，按 task_id 订阅）

详见 `src/podlator/logging.py`。

---

## 8. 配置规范

- **所有配置走 `pydantic-settings`**（`src/podlator/config.py`）
- **从 `.env` 加载**，**不要在代码中硬编码 API key 或路径**
- **新增配置项时**：
  1. 加到 `Settings` 类
  2. 加到 `.env.example`（**带注释说明用途**）
  3. 如有合理默认值，标注 `Field(default=...)`

---

## 9. 测试规范（强制要求）

> 完整测试工程指南见 `docs/TESTING_GUIDE.md`，包括 pytest 基础、mock、fixture 等。本章是给 AI 的硬约束。

### 9.1 测试分层

| 层 | 目录 | 速度 | 外部依赖 | 何时跑 |
|---|---|---|---|---|
| **Unit** | `tests/unit/` | 毫秒 | 全 mock | 每次提交、每次保存 |
| **Integration** | `tests/integration/` | 秒 | mock HTTP，真实 SQLite | 每次提交 |
| **Smoke** | `tests/smoke/` | 分钟 | 真实 API（少量样本） | `PODLATOR_RUN_SMOKE=1` 时运行 |
| **Manual** | `tests/manual/` | 不定 | 真实 API（完整跑） | 手动执行 |

**默认行为**：`uv run pytest` 只跑 unit + integration，smoke/manual 用环境变量开关。

### 9.2 测试覆盖矩阵（每个新增/修改的代码必须满足）

| 改动类型 | 必须新增的测试 |
|---|---|
| **新增节点** | Unit 测试（正常路径 + 1 个失败路径 + 1 个边界情况） + Integration 测试（在 graph 中能跑通） |
| **新增 Provider** | Unit 测试（mock HTTP，覆盖正常 + 4xx + 5xx + 超时） + Smoke 测试（真实 API，可选跳过）|
| **新增 API 路由** | Unit 测试（用 `httpx.AsyncClient`） + 边界条件测试（无效输入、未授权）|
| **新增数据库操作** | Integration 测试（用真实 SQLite + 临时数据库 fixture）|
| **修复 bug** | **先写一个能复现该 bug 的测试**，确认它失败，再修代码，确认它通过（回归测试）|
| **重构** | 不改测试，重构后必须所有原测试通过 |
| **修改 prompt** | 在 `tests/prompts/` 跑评估脚本（如有），人工 review 至少 3 个样本 |

### 9.3 测试目录结构

```
tests/
├── conftest.py                       # 全局 fixture
├── fixtures/                         # 测试数据
│   ├── audio/
│   │   └── sample_30s.mp3
│   ├── deepgram_response_full.json
│   ├── deepseek_response_summary.json
│   └── transcripts/
│       └── sample_transcript.json
│
├── unit/                             # 单元测试
│   ├── graph/
│   │   ├── nodes/
│   │   │   ├── test_fetch_metadata.py
│   │   │   ├── test_download_audio.py
│   │   │   ├── test_transcribe.py
│   │   │   └── ...
│   │   ├── test_state.py
│   │   └── test_builder.py
│   ├── providers/
│   │   ├── stt/
│   │   │   ├── test_deepgram.py
│   │   │   └── test_mlx_whisper.py
│   │   └── llm/
│   │       ├── test_deepseek.py
│   │       └── test_claude.py
│   ├── storage/
│   │   └── test_db.py
│   └── api/
│       └── test_routes.py
│
├── integration/                      # 集成测试
│   ├── test_pipeline_short_audio.py  # 端到端跑 30 秒音频
│   ├── test_pipeline_resume.py       # checkpoint 恢复
│   └── test_websocket_logs.py        # WebSocket 日志推送
│
├── smoke/                            # 真实 API 验证
│   ├── test_deepgram_real.py
│   ├── test_deepseek_real.py
│   └── test_claude_real.py
│
└── manual/                           # 手动跑的完整流程
    └── test_full_episode.py
```

### 9.4 测试编写硬规则

**Unit 测试必须**：
- **快**：单文件 < 5 秒，单用例 < 100ms
- **隔离**：不读写真实文件系统（用 `tmp_path` fixture）、不打真实 API
- **确定**：不依赖时间、网络、随机数（如必须，用 mock）
- **独立**：测试间无顺序依赖（pytest-randomly 应能随机顺序跑过）
- **可读**：测试名说清"测什么"，如 `test_transcribe_falls_back_to_local_when_deepgram_returns_429`

**Mock 规则**：
- **HTTP 调用**：用 `pytest-httpx` 的 `httpx_mock` fixture
- **时间**：用 `freezegun` 或 `time-machine`
- **环境变量**：用 `monkeypatch.setenv`
- **文件路径**：用 pytest 内置 `tmp_path` fixture
- **不要 mock 自己的代码**：mock 应该停在"系统边界"（HTTP、文件、时钟），自己写的函数直接调

**Fixture 优先级**：
1. 局部 fixture（写在测试文件顶部，只本文件用）
2. 模块 fixture（写在 `conftest.py` 同目录，只该目录用）
3. 全局 fixture（写在 `tests/conftest.py`，所有测试用）—— **慎用，全局 fixture 多了会失控**

### 9.5 覆盖率门槛

- **新增代码 ≥ 80%**（用 `pytest --cov` 检查 git diff 范围）
- **整体 ≥ 70%**（项目级别，可逐步提升）
- **核心节点 ≥ 85%**（graph/nodes 下所有文件）
- **Provider ≥ 80%**

**不要为了凑覆盖率写无意义测试**。如果一段代码确实测不了（如 `__repr__`、纯透传），可以加 `# pragma: no cover` 注释。

### 9.6 运行命令速查

```bash
uv run pytest                              # 跑所有非 smoke 测试
uv run pytest -v                           # 详细输出
uv run pytest tests/unit/                  # 只跑单元测试
uv run pytest -k "transcribe"              # 跑名字含 transcribe 的
uv run pytest -x                           # 第一个失败就停
uv run pytest --lf                         # 只跑上次失败的
uv run pytest -p no:randomly               # 关闭随机顺序
uv run pytest --cov --cov-report=term-missing  # 覆盖率（带缺失行）
uv run pytest --cov --cov-fail-under=70    # 覆盖率低于 70% 则失败

PODLATOR_RUN_SMOKE=1 uv run pytest tests/smoke/    # 跑 smoke 测试
```

### 9.7 反模式（禁止）

- ❌ **测试中调用真实 API**（除 smoke 测试外）
- ❌ **测试中 sleep**（用 `pytest.mark.asyncio` + mock 时间）
- ❌ **断言"调用过"而不验证结果**（`mock.called` 只验证副作用，要测真实返回）
- ❌ **过度 mock**（mock 自己写的函数，本质上测的是 mock 而非真代码）
- ❌ **测试有顺序依赖**（用 fixture 重建状态，不要靠"上一个测试留下的"）
- ❌ **一个测试断言一堆东西**（一个测试聚焦一个行为，多个断言只能是"同一行为的多个角度"）
- ❌ **忽略 flaky 测试**（出现一次失败就修，不要 `@pytest.mark.flaky`）

---

## 10. 关键设计决策（FAQ）

### 为什么 Python 后端 + JS 前端？

音频处理、AI 推理 80% 库在 Python（mlx-whisper、pyannote、yt-dlp）。用户的 JS 实力放在前端。这是**务实选择**，不要质疑。

### 为什么 LangGraph 而不是 LangChain？

LangChain 抽象太厚，breaking change 太频繁；LangGraph 专注做对一件事（状态机编排），适合"长任务 + 断点续传 + 可观察"的场景。

### 为什么 SQLite？

自用单机，零运维，文件级备份。未来要换 Postgres 改一行连接串。LangGraph checkpoint 也用 SQLite（`AsyncSqliteSaver`）。

### 为什么 Provider 接口抽象？

用户要"混合策略"，**切换 provider 应该是改配置而非改代码**。所有节点只依赖接口，不依赖具体厂商。

### 为什么 Prompts 独立成 Markdown？

Prompt 是核心资产，要版本化、可读、可让用户自己改而不需要碰代码。位置：`src/podlator/prompts/*.md`。

### 节点失败如何处理？

- **可重试的（网络抖动、API rate limit）**：节点内部用 `tenacity` 重试 2-3 次
- **不可重试的（音频损坏、URL 无效）**：抛 `NodeError(retryable=False)`，graph 进入 failed 终态
- **可降级的（云 STT 失败）**：fallback 到本地 STT（Milestone 4 实现），不中断 pipeline

### Web UI 如何拿到实时日志？

- 后端 `structlog` 写文件的同时通过 **WebSocket** 推送给前端
- 前端按 `task_id` 订阅，实时渲染
- 实现位置：`src/podlator/api/ws.py`

### 为什么测试要分四层？

- Unit 快但能覆盖逻辑细节
- Integration 验证组件协作
- Smoke 偶尔验证真实 API（避免厂商悄悄改 API 我们不知道）
- Manual 完整跑（发版前 / 重大改动后）

这是工业界标准分层（参考 Google 的 Testing Pyramid）。

---

## 11. 当前阶段

参考 `docs/ROADMAP.md`。**当前应该聚焦的 Milestone**：

> **Milestone 0**：项目骨架（配置、日志、状态机、节点占位、测试框架、CLI 入口）
>
> **完成判据**：
> - `uv sync` 成功
> - `uv run pytest` 通过（即使全是占位测试）
> - `uv run podlator --help` 能输出帮助信息
> - `uv run uvicorn podlator.api.main:app` 能启动
> - 前端 `pnpm dev` 能跑起一个空白页面
> - 测试基础设施齐全：`conftest.py` + 全局 fixtures + 覆盖率配置 + 至少每个节点一个占位测试

完成 M0 后再开始 **Milestone 1**（实现 Deepgram + DeepSeek + Claude 真实调用，跑通第一期完整 pipeline）。

**重要**：不要跳跃式开发。先把骨架做扎实，节点占位完整，再逐个填充实现。

---

## 12. 如果你遇到困难

- **设计选择有疑虑** → 停下来，列出选项和取舍，问用户
- **依赖冲突或版本问题** → 优先用 `uv` 解决，搞不定就说明现状，问用户
- **测试一直跑不过** → 不要为了通过测试改测试断言，先理解为什么失败
- **不确定某个 API 的真实行为** → 写一个最小 repro 脚本验证，**不要凭记忆写代码**
- **改动很大不确定方向** → 写一份简短的 RFC 放在 `docs/rfc/<topic>.md`，让用户先审

记住：**慢一点没关系，但要做对。** 用户更看重架构质量而不是开发速度。

---

## 13. Definition of Done（DoD）—— 完成判据强制清单

> **任何"完成一项需求"的宣告，必须满足以下全部条件。少一项都视为未完成。**
>
> AI 在每次完成功能后，必须在最后输出中**逐项确认**这份清单。

### 13.1 代码质量

- [ ] 所有新增 / 修改的代码都有**类型注解**
- [ ] `uv run ruff check .` 通过（无 lint 错误）
- [ ] `uv run ruff format --check .` 通过（格式正确）
- [ ] `uv run mypy src/` 通过（无类型错误）

### 13.2 测试

- [ ] 新增 / 修改的代码都有**对应单元测试**
- [ ] 涉及多节点协作的改动有**集成测试**覆盖
- [ ] 每个外部依赖至少测了一个**失败场景**（4xx / 5xx / 超时 / 数据异常）
- [ ] 每个公共函数测了至少一个**边界条件**（空输入、超长、None）
- [ ] **修复 bug 必须先写复现测试**（确认它失败，再修，再确认通过）
- [ ] `uv run pytest` **全绿**（无 fail、无 error，warning 可接受）
- [ ] `uv run pytest --cov --cov-fail-under=70` 通过
- [ ] 新增代码覆盖率 ≥ 80%（用 `pytest --cov` 检查输出）
- [ ] 无被忽略 / 跳过的测试（除非有明确注释说明为什么）

### 13.3 日志与可观察性

- [ ] 关键路径都有结构化日志（按第 7.3 节必填字段表）
- [ ] 所有 `try/except` 都有 log（无静默吞异常）
- [ ] 外部 API 调用都记录了**耗时和成本**
- [ ] 日志级别使用正确（DEBUG/INFO/WARNING/ERROR/CRITICAL）
- [ ] 无 `print()` 调用残留

### 13.4 文档

- [ ] `CHANGELOG.md` 已追加本次改动条目
- [ ] 如改了使用方式 → `README.md` 已更新
- [ ] 如改了架构 / 约定 → `CLAUDE.md` 已更新
- [ ] 如新增了节点 → `docs/ARCHITECTURE.md` 节点列表已更新
- [ ] 新增配置项 → `.env.example` 已更新

### 13.5 可执行验证

- [ ] `uv sync` 成功
- [ ] 项目能正常启动:`uv run uvicorn podlator.api.main:app`
- [ ] 如涉及前端，`cd web && pnpm build` 成功

### 13.6 自检输出格式

每次完成功能后，AI 必须在最后输出中按以下格式自检：

```
## DoD 自检

### 代码质量
- [x] 类型注解齐全
- [x] ruff check 通过
- [x] ruff format 通过
- [x] mypy 通过

### 测试
- [x] 新增 3 个单元测试：test_xxx, test_yyy, test_zzz
- [x] 新增 1 个集成测试：test_aaa
- [x] 失败场景测试：超时、API 5xx
- [x] 边界条件测试：空输入
- [x] pytest 全绿：23 passed, 0 failed
- [x] 覆盖率：本次新增代码 87%，整体 73%

### 日志
- [x] 节点入口/出口日志齐全
- [x] API 调用日志带 cost_usd 和 duration_ms
- [x] 无 try/except 静默吞异常

### 文档
- [x] CHANGELOG.md 已更新
- [x] CLAUDE.md 无需更新（未改架构）
- [x] README.md 无需更新（未改使用方式）

### 验证
- [x] uv sync 成功
- [x] uvicorn 能启动
- [x] CLI 能调用

✅ 本次改动满足 DoD，可以提交。
```

**任何一项标红（未通过）→ 立刻修复或回滚，不要试图绕过。**
