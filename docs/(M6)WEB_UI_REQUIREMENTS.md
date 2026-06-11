# Web 端需求定义（M6 预研）

> 状态：**需求定义阶段**，未排期。本文档定义目标、选型结论、功能边界与关键决策点；详细任务书在排期后由规划者按里程碑产出。
> 阅读对象：统筹者（决策）、规划者（出任务书时的依据）。

---

## 1. 愿景与目标

**近期目标**：Web 端取代 CLI 成为日常主操作方式——
- 浏览器上传 SRT 字幕（或粘贴 URL），配置参数，一键跑完整口播稿链路
- 看到历史任务记录：什么时候生成的、用了什么参数、花了多少钱
- 看到每一步的产物：素材笔记、蓝图、素材卡、草稿、评分报告、终稿（M5 落盘的全部中间产物）
- 任务失败时从失败步骤重跑，不用从头再来

**远期愿景**（自动化终态）：
```
任意入口（飞书 bot / iOS 快捷指令 / 订阅监控 D2）
  → POST /api/tasks（一个链接或一个文件）
  → 全自动链路（下载/解析 → digest → blueprint → research → finalize → review loop [→ TTS]）
  → 通知回执（成品链接推送回来）
```
Web 端做好 API 化之后，"发个链接全自动出成品"不需要单独开发——它只是给同一个 API 多接一个触发器。

## 2. 现状盘点（重要：不是从零开始）

M2 已交付一套完整可跑的 Web MVP（面向旧的「URL → 中文简报」工作流）：

| 层 | 已有资产 | 状态 |
|---|---|---|
| 后端 API | `POST/GET/DELETE /api/tasks`、`/tasks/{id}/retry`、`/tasks/{id}/brief`（`src/podlator/api/routes.py`） | ✅ 可跑，带测试 |
| 实时日志 | structlog → LogHub → WebSocket 按 task_id 订阅（`api/ws.py`、`api/log_hub.py`） | ✅ 可跑 |
| 任务存储 | SQLite `TaskStore`（`storage/db.py`，aiosqlite） | ✅ 可跑，但 schema 面向 URL 任务 |
| 前端 | Vite + React + TanStack Query + shadcn/ui 风格；SubmitPage / QueuePage / TaskDetailPage / BriefViewerPage + 组件测试（`web/src/`） | ✅ 可跑，面向旧工作流 |

**缺口**（本需求的实际工作量所在）：
1. 任务模型只认 `source_url`，不支持 SRT 上传与多任务类型
2. 任务执行挂的是旧 LangGraph 简报 pipeline，douyin 链路（steps/）没接入
3. 没有"步骤级"运行记录（每步状态/产物/耗时/成本），任务只有整体状态
4. 前端没有分步产物查看、评分报告展示、参数配置

## 3. 选型分析与结论

### 3.1 四个候选方案对比

| 维度 | A. 自建 Web（现有栈） | B. n8n 拖拽编排 | C. 飞书多维表格 | D. Streamlit/Gradio |
|---|---|---|---|---|
| 核心逻辑承载 | Python steps 层（已有，已测试） | 需重写进 n8n 节点（JS）或 n8n 只当壳 | 不能承载，只能展示 | Python 但 UI 天花板低 |
| 本机 CLI 依赖（claude/codex 会员态） | 原生支持 | Docker 内调宿主 CLI，别扭 | 不可行 | 支持 |
| 长文稿阅读/对比体验 | 完全可控（已有 Markdown 渲染组件） | 执行历史 UI 不适合读 6000 字 | 多维表格大文本体验差 | 一般 |
| 可测试性（项目三大特性之一） | pytest + vitest 全覆盖（已有惯例） | n8n 流程无法进测试体系 | 无 | 弱 |
| 已有投入 | **M2 已交付 60% 基础** | 从零 | 从零 | 从零 |
| 维护风险 | 范围蔓延致臃肿（可用约束控制，见 3.3） | 双系统维护（流程定义 + Python） | 依赖飞书生态/权限/token | 需求一复杂就重写 |
| 适用场景本质 | 自研 pipeline 的控制台 | 串现成 SaaS 的胶水 | 轻量看板/通知 | 内部演示工具 |

### 3.2 结论

**主方案 A：在现有自建 Web 上改造升级。** 三个决定性理由：

1. **n8n 式编排解决的不是你的问题**。拖拽画布的价值在"自由重组流程"，但口播稿链路是**固定的线性流程**，你真正要的是：看到每步状态、查看每步产物、失败重跑——这是"流水线监控面板"需求，不是"工作流编排器"需求。把需求降维后，自建的工作量小一个数量级。而 n8n 的代价是真实的：核心逻辑要么重写（丢掉整个 Python 测试体系），要么 n8n 退化成只调 API 的壳（那它提供的只剩一层不可测试的皮）。
2. **你的技术画像站在自建这边**。维护担忧对"后端工程师硬写前端"成立，但 React 是你的主场；且 M2 的存量代码已验证这条路走得通。
3. **飞书定位为通知渠道，不是操作界面**（进 Backlog）：任务完成后推卡片消息很合适；但上传文件、读长稿、看 diff、重跑步骤在多维表格里都别扭，且数据与本地产物文件系统割裂。

### 3.3 防臃肿三约束（写进架构，不是口头承诺）

你担心的"后期维护臃肿"，根源是范围蔓延而不是技术栈。用三条硬约束控制：

1. **Web 层零业务逻辑**：所有生成逻辑留在 `steps/` 层（被 pytest 覆盖）。API 层只做四件事：任务 CRUD、触发执行、流式日志、产物文件服务。判据：删掉整个 `api/` + `web/`，CLI 功能不受任何影响。
2. **页面预算 5 个封顶**：提交页、任务列表页、任务详情页（含步骤时间线）、产物阅读页、设置页（后期可选）。新页面需求出现时，先问"能不能塞进现有页面"，不能就进 Backlog 排队，不立刻做。
3. **产物只读**：Web 端不做在线编辑器。看稿、复制、下载；改稿用本地编辑器（产物本来就在文件系统里）。在线编辑是公认的复杂度黑洞，明确不做。

### 3.4 数据库：SQLite，不引入 Docker MySQL（需统筹者确认的反对意见）

你提出 Docker MySQL，**我的建议是维持 SQLite**，理由：

- 单机自用、并发是"一个人点几下"的量级——SQLite 是这个场景的标准答案，也是项目既有约定（CLAUDE.md FAQ：「自用单机，零运维，文件级备份」），现有 TaskStore 已经是 SQLite 实现
- 你要的"启动和迁移方便"恰恰是 SQLite 的强项：**零容器、零端口、零密码管理，备份 = 复制一个文件**；Docker MySQL 反而引入容器启停顺序、数据卷备份、连接配置三件新运维事
- 兜底未来：数据访问保持在 TaskStore 一层（不在路由里写裸 SQL），schema 设计避开 SQLite 专属特性。真到需要多机/远程访问那天，按项目 FAQ 的原话"改一行连接串"迁 MySQL/Postgres，且历史数据一个文件就能导走
- 迁移管理：schema 变更用顺序迁移脚本（`storage/migrations/` 目录 + 启动时按版本号执行），不引入 Alembic 这种重依赖，对单机够用

## 4. 功能需求定义

### 4.1 MVP（M6 范围）

**F1 任务提交**
- 上传 SRT 文件（拖拽/选择），填写：标题（必填）、目标字数（默认 6000）、是否跳过 assign-speakers、provider 覆盖（默认读 `.env`）、series 资产开关（M5.5 后）
- 兼容旧入口：粘贴 URL 创建「URL → 简报」任务（保留能力，不重点投入）
- 提交后立即返回任务页，全自动执行（无人工暂停点，与 M5 决策一致）

**F2 任务列表（历史记录）**
- 全部任务：状态（排队/运行中/完成/失败）、标题、类型、创建时间、总耗时、**总成本**（按步聚合 cost_usd）
- 状态筛选 + 标题搜索；运行中任务自动刷新（轮询或 WS）

**F3 任务详情：步骤时间线**（本需求的核心页面）
- 链路每步一行：`parse-srt → assign-speakers → digest → blueprint → research → finalize → review(N轮) → 终稿`
- 每步显示：状态、耗时、成本（tokens/cost_usd，来自现有结构化日志字段）、产物入口按钮
- 实时日志面板：复用现有 WebSocket LogViewer，按步骤名过滤
- **失败步重跑**：上游产物已落盘 → 从失败步继续，不重跑全链路；可改参数后重跑（如换 finalize provider）

**F4 产物阅读**
- Markdown 渲染（复用 BriefRenderer）：素材笔记、蓝图、素材卡（JSON 表格化展示来源链接）、各轮草稿、终稿
- 评分报告专属视图：维度分数条 + 证据引用 + 修订指令列表（消费 M5.1 的 `*.review.json`）
- 每个产物：复制 / 下载；终稿与上一轮草稿的 diff 视图（后期，见 4.2）

**F5 API 触发（远期愿景的地基，MVP 就做）**
- `POST /api/tasks` 支持纯 JSON 调用（`{type, input, params}`），不依赖浏览器表单——这一个端点就是未来 bot/快捷指令/订阅监控的统一入口

### 4.2 后期（进 Backlog，不在 M6 做）

- 草稿轮次 diff 视图、评分趋势图（跨期 judge 分数曲线）
- 飞书通知：任务完成/失败推卡片（替代你刷新页面）
- TTS 串联展示与音频试听（依赖 Backlog B3）
- 订阅收件箱页面（依赖 D2：每天候选蓝图列表 + 一键批准）
- 设置页：provider/默认参数/series 资产编辑

### 4.3 明确不做

- ❌ 在线 Markdown 编辑器（产物只读，改稿走本地编辑器）
- ❌ 拖拽式流程编排画布（流程固定，不存在重排需求）
- ❌ 用户系统/多租户/鉴权（单机自用，监听 localhost）
- ❌ 移动端深度适配（能看即可，操作以桌面为准）

## 5. 架构概要

### 5.1 数据模型草案（SQLite）

```
tasks（泛化现有表）
  id TEXT PK
  task_type TEXT          -- 'srt_douyin' | 'url_brief'
  title TEXT
  status TEXT             -- queued | running | completed | failed
  input_ref TEXT          -- SRT 文件路径 或 URL
  params_json TEXT        -- target_words / providers / digest_mode / series_dir ...
  cost_usd_total REAL
  error_msg TEXT
  created_at / updated_at

task_steps（新增：步骤级运行记录，Web 时间线的数据源）
  id INTEGER PK
  task_id TEXT FK
  step_name TEXT          -- parse_srt / digest / blueprint / research / finalize / review_r1 ...
  status TEXT             -- pending | running | completed | failed | skipped
  started_at / finished_at / duration_ms
  artifact_path TEXT      -- 落盘产物路径（产物本体永远在文件系统，DB 只存路径）
  tokens_in / tokens_out / cost_usd
  error_type / error_msg
```

设计原则：**大文本不进数据库**。产物继续按项目惯例落盘（M5 已建立 `*.digest.json` / `*.blueprint.md` / `*.research.json` / `*.review.json` 约定），Web 通过 `GET /api/tasks/{id}/artifacts/{step}` 读文件返回。这也是 SQLite 足够用的原因之一。

### 5.2 任务执行层（关键决策点，见第 6 节）

新增一个轻量 task runner（service 层）：顺序执行 steps、每步前后写 `task_steps` 记录、产物落盘、异常归类（复用 `ProviderError.retryable`）。CLI 与 Web 共用这一层——`pipeline-douyin` 命令重构为调用同一个 runner，保证两个入口行为一致、测试只写一份。

### 5.3 与 M5 的衔接

**建议顺序：M5.1 → M5.4 完成后启动 M6**（M5.5 节目化可与 M6 并行）。理由：
- M6 的核心页面（步骤时间线 + 产物查看）展示的正是 M5 落盘的中间产物——M5.4 把链路串稳、产物 schema 定型之后，Web 才有稳定的数据契约，否则前后端跟着 M5 的改动返工
- 反向依赖不存在：M5 全部通过 CLI 可验收

## 6. 关键决策点（需统筹者拍板）

| # | 决策 | 规划者建议 | 待确认 |
|---|---|---|---|
| 1 | 数据库 | SQLite（理由见 3.4），不引入 Docker MySQL | ⬜ |
| 2 | 任务编排层 | 轻量 task runner（5.2），douyin 链路**不**迁入 LangGraph。理由：链路线性，LangGraph 的图编排/checkpoint 价值可由 task_steps + 产物落盘等价实现，且迁移与 M5 改动冲突面大。**注意**：这意味着 CLAUDE.md「架构核心 = LangGraph」的表述需修订（LangGraph 保留给旧 URL 简报工作流），属项目级约定变更 | ⬜ |
| 3 | M5/M6 顺序 | M5 先行，M6 在 M5.4 验收后启动 | ⬜ |
| 4 | 旧「URL→简报」工作流在 Web 中的地位 | 保留入口、维持现状、不投入新功能 | ⬜ |

## 7. 里程碑切分建议（确认后出详细任务书）

| 里程碑 | 内容 | 粗估工作量（AI 执行节奏） |
|---|---|---|
| M6.1 后端 | tasks 表泛化 + task_steps 表 + 迁移脚本；task runner（CLI/Web 共用）；SRT 上传与任务创建端点；产物读取端点；douyin 链路接入 | 2–3 天 |
| M6.2 前端 | 提交页改造（SRT 上传+参数）；任务详情页步骤时间线；产物阅读器 + 评分报告视图；列表页成本/类型列 | 3–4 天 |
| M6.3 触发器 | `POST /api/tasks` JSON 调用打磨 + 第一个外部触发器（飞书 bot 或 快捷指令，二选一）+ 完成通知 | 1–2 天 |

测试策略沿用 M5 总纲：unit/integration 全 mock（API 层用 `httpx.AsyncClient`，前端 vitest + Testing Library，与 M2 既有惯例一致）；真实链路验收每里程碑一次。
