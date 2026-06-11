# M5 — 口播稿质量飞跃（总览）

> **本文件是 M5 阶段的总规划，面向统筹者（人类）和执行者（AI CLI）。**
> 编号说明：ROADMAP 的 M4 已被「本地 STT 兜底」占用，本阶段编号为 M5，与 STT 兜底无依赖关系，优先级由统筹者另行安排。
>
> 执行任何子任务前，必须先读 `docs/tasks/EXECUTION-FRAMEWORK.md` 和 `CLAUDE.md`（重点第 7、9、13 章）。

---

## 1. 背景：三个已确认的结构性问题

| # | 问题 | 证据 |
|---|---|---|
| 1 | **输入截断**：`douyin_script.py` 的 `DEFAULT_MAX_INPUT_CHARS = 36000`，而 12 期素材正文实测 58,746–137,080 字符，每期有 40%–75% 的访谈内容被静默丢弃，蓝图与成稿只基于访谈前段写成 | 实测 `project/*/` 全部 12 期 SRT |
| 2 | **外部知识不可靠**：成稿中"金融时报报道过"等引用全部来自模型参数记忆，无任何验证环节；同时用户差距分析认定"外部知识深度"是 v2 后最大剩余差距 | `docs/goal目标制定/差距分析-三篇产出vs黄金样本.md` 第 193 行 |
| 3 | **质量评估靠人工**：六维评分体系存在但需人肉重评；字数补足回路是尾部追加式，破坏已收束的结尾；蓝图不落盘，不可观察 | 同上文档 + `douyin_script.py` `_supplement_words_loop` |

> **横切病症：静默截断（三个边界）。** 上表问题 #1（输入截断）其实只是同一种病的一个面。`docs/max-tokens-问题说明.md` 暴露了另外两个面：**输出截断（说话人）**——`assign_speakers.py` 分片 JSON 被 `max_tokens=8192` 截断后整片丢标签；**输出截断（定稿）**——`_complete_with_fallback` 调用 finalize 时根本没传 max_tokens，降级到 DeepSeek/Claude API 时 6000 字定稿被腰斩。三处共同的病根是**没人读 `finish_reason`**，截断永远是「悄悄丢数据」而非「一条 warning」。M5 把这三个边界分别消灭：检测基础设施 + 说话人面 → **M5.0**；输入面 → **M5.2**；定稿面 → **M5.4**；并在 **M5.1** 的 lint 里装一个永久跳闸器，让截断的稿子再也无法静默通过。

## 2. M5 目标与新链路

全自动（无人工暂停点）、全程可观察（中间产物全部落盘）、效果可度量（LLM judge 回归）。

```
SRT
 → parse-srt                      （已有，不动）
 → assign-speakers                （已有，不动）
 → digest        [M5.2 新增]       全文分段精读 → 素材笔记 *.digest.json
 → blueprint     [M5.2/5.3 改造]   输入素材笔记（不再截断原文）；输出含研究问题清单 → *.blueprint.md
 → research      [M5.3 新增]       codex --search 联网查证 → 素材卡 *.research.json（失败可跳过）
 → finalize      [M5.2/5.3 改造]   蓝图 + 素材笔记 + 素材卡 → 草稿（外部知识只准引用素材卡）
 → review loop   [M5.4 新增]       lint（程序检查）+ judge（M5.1）→ 修订指令 → 定点重写，≤2 轮
 → 终稿 + *.review.json
```

M5.0（截断加固）不新增节点，横向加固既有链路的入口（`assign-speakers`）+ provider 层 + 配置，消灭三个边界的静默截断，是 M5 的质量地基（脏的说话人标签会污染 digest → 污染全链路）。
M5.5（节目化资产）横切注入 blueprint / finalize 的 prompt。

## 3. 子任务总表与依赖

| 子任务 | 名称 | 状态 | 依赖 | 任务书 |
|---|---|---|---|---|
| M5.0 | 截断加固（finish_reason + assign-speakers） | ✅ 已完成 | 无 | `docs/tasks/M5.0-truncation-hardening.md` |
| M5.1 | Eval 体系与评分标准 v3 | ✅ 已完成 | 无 | `docs/tasks/M5.1-eval-system.md` |
| M5.2 | 全文消化（digest + 链路改造） | **当前任务** | M5.0 + M5.1 | `docs/tasks/M5.2-digest.md`（已细化到文件级） |
| M5.3 | Codex 联网 research（+ 拆 blueprint/finalize 公共 step） | 已细化（见任务书）¹ | M5.2 | `docs/tasks/M5.3-research.md` |
| M5.4 | 审稿循环 + 事实核查 | 已细化（见任务书）¹ | M5.0 + M5.1 + M5.2 + M5.3 | `docs/tasks/M5.4-review-loop.md` |
| M5.5 | 节目化资产注入 | 已细化（见任务书）¹ | M5.3（公共 step 槽位）；可与 M5.4 并行 | `docs/tasks/M5.5-series-assets.md` |

> ¹ M5.3/5.4/5.5 的任务书是**在 M5.2 执行落地前、基于 M5.2 锁定的契约提前写的**。执行顺序仍是一次一本、过审再下一本（见下方工作流程）；**每本开工前先核对前序任务实际落地的签名/产物，有出入先校正任务书再动手**（各书开头已注明此「复核」要求）。digest schema 或公共 step 签名若在执行中调整，后续书需同步。

**为什么 M5.0 最先**：它是 bug 修复也是地基。`assign-speakers` 截断会让一整片字幕丢说话人标签，脏标签往下游 digest → finalize 一路污染；而它交付的 `finish_reason` 检测被 M5.2（输入面）、M5.4（定稿面）、甚至 M5.1 的 judge（judge 输出 JSON 被截断正是要防的场景）共享。先把地基打平，后续改动才不在流沙上盖楼。M5.0 与 M5.1 互相独立，可并行，但建议先合入 M5.0。

**为什么 M5.1 紧随其后**：后续每个改动（全文消化是否真的提升覆盖、research 是否真的提升外部知识质量）都需要 judge 给出客观回归信号。没有度量就没有优化。

**工作流程**：执行者完成一个子任务 → 按 EXECUTION-FRAMEWORK 格式提交完成报告 → 统筹者把报告交给规划者审核 → 审核通过后规划者产出下一份详细任务书。**不要跳过审核直接开下一个任务。**

## 4. 各子任务模块级规划

> M5.0、M5.1 的文件级细节见各自专属任务书，此处不重复。以下为 M5.2–M5.5 的模块级规划（实现细节以届时的详细任务书为准）。

### M5.0 — 截断加固（已细化，见 `docs/tasks/M5.0-truncation-hardening.md`）

**核心改动**（一句话回顾，细节在专属任务书）：
- `LLMResult` 增加 `finish_reason`；DeepSeek/Claude provider 截断（`finish_reason == "length"`）即 `log.warning("llm_output_truncated", ...)`——三处共享的检测地基。
- `assign-speakers` 分片 80→50；`_parse_llm_content` 在 JSON 截断时**正则抢救已完成的对象**（73 条完整就救回 73 条，只丢残缺的第 74 条），不再整片返回 `{}`。
- `deepseek_max_tokens` 8192→32768、`claude_max_tokens` 4096→8192（抬高 API 路径的输出地板）。
- 一次真实 smoke 验证 v4-flash 是否吃 reasoning token（决定 `_SPEAKER_SHARD_MAX_TOKENS` 够不够）。

**边界划分**：M5.0 只做「检测地基 + 说话人面（A）」。定稿面（B）归 M5.4、输入面（C）归 M5.2，两者复用 M5.0 的 `finish_reason`。

### M5.2 — 全文消化（已细化，见 `docs/tasks/M5.2-digest.md`）

> 以下为模块级摘要；文件级实现细节（签名、prompt 全文、测试名+断言、真实 API 使用规约）以专属任务书为准。

**核心改动**：
- 新增 `src/podlator/steps/digest_transcript.py`：
  `async def digest_transcript(transcript: TranscriptDocument, *, provider_name: str, settings: Settings, chunk_chars: int = 30000, overlap_chars: int = 2000) -> DigestDocument`
  全文按 `chunk_chars` 分段（段落边界切分，带重叠），每段用便宜模型（DeepSeek）精读，产出素材笔记。
- 新增 `DigestDocument` pydantic 模型（`steps/models.py`）：每段含 `key_points[]`、`quotes[]`（speaker + 原话 + 时间点）、`data_points[]`（数字/金额/日期）、`terms[]`（待白话化术语）。
- 新增 prompt `src/podlator/prompts/digest_chunk.md`。
- `douyin_blueprint.md` / `douyin_finalize.md` 输入改造：`{content}` 从「截断原文」换成「素材笔记全集」（总量约 6–10k 中文字符，任何模型都舒适）。
- `--digest-mode auto|full|map`：auto（默认）= 正文 >50,000 字符走 map-reduce，否则全文直喂蓝图（短素材不增加一轮成本）；`max_input_chars` 默认提到 160,000，截断逻辑保留但触发时必须 `log.warning("transcript_truncated", dropped_chars=...)`——**静默截断是本次要消灭的 bug**（这是 M5.0「横切病症」表里的**输入面 C**）。
- **复用 M5.0 的输出截断检测**：digest 每段精读调用 DeepSeek 后检查 `result.finish_reason`（M5.0 已落地）；若某段笔记被 `== "length"` 截断，`log.warning` 并对该段重试/缩小 `chunk_chars`，避免「素材笔记自己先被截断」削弱覆盖。
- 中间产物落盘：`*.digest.json`、`*.blueprint.md`（落盘是可观察性要求，不是人工暂停点，pipeline 全自动直通）。

**验收**（届时任务书细化）：
- 程序断言：第 12 期 digest 产物中存在时间点 > 总时长 85% 的素材条目（证明访谈尾部进入了视野）。
- judge 对比：同一期「旧截断蓝图」vs「新全文蓝图」各生成一稿，M5.1 judge 评分，信息覆盖度维度新版应显著更高。

### M5.3 — Codex 联网 research（已细化，见 `docs/tasks/M5.3-research.md`）

> 以下为模块级摘要；文件级细节以专属任务书为准（含 blueprint/finalize 拆公共 step）。

**核心改动**：
- `providers/llm/cli_tool.py`：新增 search 能力，工厂注册独立 provider 名 `codex_search_cli`（按 `docs/CODEX_CLI_NON_INTERACTIVE.md` 的长期建议拆分，便于日志与降级区分）。
  ⚠️ 关键细节：`--search` 是**顶层全局参数，必须放在 `exec` 之前**（`codex --search exec ...`），放错位置会静默失效。
- 新增配置：`llm_provider_research`（默认 `codex_search_cli`）。
- `douyin_blueprint.md` 改造：「外部知识补充点」从自由文本改为结构化**研究问题清单**（固定格式，可程序解析）。
- 新增 `src/podlator/steps/research_facts.py`：研究问题清单 → 逐条（或合批）调用 codex search（用 `--output-schema` 强制 JSON）→ `ResearchDocument` 素材卡落盘 `*.research.json`。
- 素材卡 schema：`{question, findings: [{claim, source_name, source_url, published_date, confidence: high|medium|low}], status: confirmed|partial|not_found}`。
- `douyin_finalize.md` 改造（**硬约束**）：外部知识**只允许**引用素材卡内容并带来源名；素材卡为空/缺失时进入「宁缺毋滥」模式——不编造，外部知识可少于 3 处。
- 降级路径：codex 不可用 / 超时 / search 失败 → research 整步跳过，`log.warning("fallback_triggered", reason=...)`，pipeline 继续。

**验收**：mock 覆盖超时/CLI 不存在/JSON 不符 schema；1 次真实 smoke（codex 会员额度，无现金成本）验证素材卡含真实 URL。

### M5.4 — 审稿循环 + 事实核查（已细化，见 `docs/tasks/M5.4-review-loop.md`）

> 以下为模块级摘要；文件级细节以专属任务书为准。

**核心改动**：
- 新增 `src/podlator/steps/review_script.py`：组合 M5.1 的 lint（程序检查）+ judge（语义评分）→ `ReviewReport`（分数 + `revision_directives[]` + verdict）。
- 事实核查并入 review：素材卡对照（成稿中的外部事实声明必须能在 `*.research.json` 中找到对应条目，找不到 → 生成「删除或改写」修订指令）。
- 修订：`revise_script()` —— finalize provider 接收「草稿 + 修订指令列表」→ 输出**定点重写后的全稿**（指令明确到节，禁止全文重写推翻已合格部分）。
- 循环控制：verdict 为 needs_revision 且轮数 < 2 → 修订 → 重评；达标或满 2 轮即停（最终 verdict 记入 `*.review.json`）。
- **删除 `_supplement_words_loop`**：字数不足改由 lint 检出 → 变成修订指令（"主题 X 未达预算，扩写该节"）→ 定点重写。尾部追加式补字（破坏结尾收束）从此移除。
- **消灭定稿截断（M5.0「横切病症」表里的输出面 B）**：现状 `_complete_with_fallback` 调 finalize 时**根本没传 `max_tokens`**，走 CLI 侥幸没事，一旦降级到 DeepSeek/Claude API 就被默认上限腰斩。重写 `revise_script()` / finalize 调用时**必须按 `target_words` 显式传 `max_tokens`**（约 `字数 × 2.2 + 余量`），并用 M5.0 的 `result.finish_reason == "length"` 作为「定稿被截断」的断言信号（截断即判 needs_revision 并重试，绝不让半截稿进 review）。M5.0 已把 config 默认地板抬到 32K/8K，这里再按目标字数精确覆盖。
- `pipeline-douyin` 串联全链路（digest → blueprint → research → finalize → review loop），全部中间产物落盘。

**验收**：mock 全链路 integration；真实 manual 验收一期（见第 5 节第 4 层）。

### M5.5 — 节目化资产（已细化，见 `docs/tasks/M5.5-series-assets.md`）

> 以下为模块级摘要；文件级细节以专属任务书为准。

**核心改动**：
- 新增 `project/series/` 资产目录：`series.md`（栏目名、解说者人设与口头禅、自称）、`glossary.md`（跨期术语表：inference→推理 等）、`episodes.md`（往期选题与一句话核心论点，供跨期引用）。资产初稿由规划者起草、统筹者终审（人设措辞是产品决策）。
- 新增 `src/podlator/steps/series_context.py`：读取资产 → 格式化为 prompt 注入块；目录缺失时返回空串并 `log.info("series_context_missing")`，不报错。
- `douyin_blueprint.md` / `douyin_finalize.md` 增加可选 `{series_context}` 槽位。
- CLI `--series-dir` 参数；`pipeline-douyin` 默认探测 `project/series/`。
- 每期完成后向 `episodes.md` 追加一行（自动）。

**验收**：unit（注入 / 缺失优雅跳过 / 术语表生效）；真实跑一期人工检查跨期引用是否自然。

## 5. 测试策略总纲（全阶段适用）

沿用项目四层测试体系，**费用控制三道闸门**：

| 层 | 触发方式 | LLM 调用 | 费用 | 何时跑 |
|---|---|---|---|---|
| 1. Unit | `uv run pytest` 默认 | 全 mock | ¥0 | 每个 Phase 验证 |
| 2. Integration | `uv run pytest` 默认 | 全 mock，真实文件流 | ¥0 | 每个子任务最终验证 |
| 3. Smoke | `PODLATOR_RUN_SMOKE=1` 显式开启 | 真实 API，**小样本** | 见预算表 | 每个子任务收尾一次 |
| 4. Manual 验收 | 统筹者陪跑 | 真实 API 全流程 | 见预算表 | M5.4 完成后 + M5.5 完成后各一次 |

**硬规则**：
- 开发期间一律 mock（fixtures 放 `tests/fixtures/`，从 12 期真实产物截取小样本，不调 API）。
- Smoke 测试必须在测试名/输出中标注预估费用；执行者不得在 unit/integration 层调真实 API（违反即打回）。
- Manual 验收用第 12 期（Dylan Patel，截断问题最严重的一期）作为基准素材，对照旧版产物。

**费用预算表**（现金部分均为 DeepSeek，单价低；CLI 调用走会员额度无现金成本）：

| 子任务 | Smoke/验收内容 | 预估现金费用 |
|---|---|---|
| M5.1 | judge 校准：评 4 个已有人工评分的样本 | ¥1–2 |
| M5.2 | 第 12 期 digest + 新旧蓝图对比 + judge 评分 | ¥2–4 |
| M5.3 | 1 次真实 codex search（会员额度）+ 解析 | <¥1 |
| M5.4 | 端到端 1 期（digest/blueprint/judge 走 DeepSeek） | ¥3–5 |
| M5.5 | 1 期含 series 注入 | ¥3–5 |
| **合计** | | **≈ ¥15 以内** |

## 6. 统筹者资源准备清单

- [x] DeepSeek API key（`.env` 已有）
- [ ] 验证 codex CLI 已登录且联网可用：`codex --search exec "请联网告诉我今天 OpenAI 官网首页标题" `（M5.3 前完成即可）
- [ ] 验证 claude CLI 已登录：`claude -p "ping" --output-format json`
- [ ] 确认允许使用 `project/` 下 12 期真实数据作为测试素材（含截取片段进 `tests/fixtures/`）
- [ ] M5.5 前：审阅规划者起草的 `series.md` 人设初稿（栏目名、口头禅是产品决策）

## 7. Backlog（本阶段明确不做）

详见 `docs/BACKLOG.md`：B2 发布配套物自动生成、B3 TTS-ready 听感处理、D2 订阅化。
另：C2 风格沉淀（用户决定不做）、B1 蓝图人工审核暂停点（用户决定全自动化，仅保留落盘）。
