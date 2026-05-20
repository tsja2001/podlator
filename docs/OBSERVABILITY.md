# 可观察性指南

> 本文档讲：日志怎么读、出问题怎么排查、Web UI 实时观测怎么用。
>
> 配套硬约束见 `CLAUDE.md` 第 7 章。本文是给"使用者"的视角——出 bug 时翻这本。

---

## 1. 三道防线

Podlator 的可观察性靠三层：

```
┌─────────────────────────────────────────────────────┐
│  第 1 层：控制台日志（开发期）                        │
│  - 彩色 pretty 输出                                  │
│  - 实时看节点进展                                    │
│  - 命令：直接看终端                                  │
└─────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────┐
│  第 2 层：JSON 日志文件（事后排查）                   │
│  - data/logs/podlator.log                            │
│  - 结构化，可 grep / jq 查询                          │
│  - 永久保留（按大小轮转）                            │
└─────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────┐
│  第 3 层：Web UI 实时面板                            │
│  - 按 task_id 订阅                                   │
│  - 节点状态可视化                                    │
│  - 命令：浏览器打开 http://localhost:5173            │
└─────────────────────────────────────────────────────┘
```

---

## 2. 日志结构

每条日志是一个 JSON 对象，关键字段：

```json
{
  "timestamp": "2026-05-19T14:23:45.123456",
  "level": "info",
  "logger": "podlator.node.transcribe",
  "event": "api_call_completed",
  "task_id": "abc-123",
  "node": "transcribe",
  "provider": "deepgram",
  "duration_ms": 4521,
  "tokens_in": null,
  "tokens_out": null,
  "audio_duration_seconds": 1800,
  "cost_usd": 0.129
}
```

**事件命名约定**（`event` 字段）：

| 事件名 | 含义 |
|---|---|
| `node_started` | 节点开始执行 |
| `node_completed` | 节点正常完成 |
| `node_failed` | 节点异常退出 |
| `api_request` | 即将调用外部 API（DEBUG 级） |
| `api_call_completed` | API 调用成功返回 |
| `api_call_failed` | API 调用失败 |
| `retry_attempt` | 重试中 |
| `fallback_triggered` | 触发降级方案 |
| `task_started` | 整个任务开始（pipeline 入口） |
| `task_completed` | 任务完成 |
| `task_failed` | 任务终止失败 |
| `checkpoint_saved` | LangGraph 保存了 checkpoint |
| `checkpoint_resumed` | 从 checkpoint 恢复 |

---

## 3. 排查问题的工作流

### 3.1 步骤模板

任何 bug 都按这个顺序查：

```
1. 找到 task_id
   ↓
2. grep 出该任务所有日志
   ↓
3. 看是哪个节点失败
   ↓
4. 看失败节点的入参（state 快照）和报错
   ↓
5. 看失败前最后一次成功的 API 调用是什么
   ↓
6. 重现 → 修复 → 写回归测试
```

### 3.2 实战命令

**找到某任务的所有日志**：

```bash
# 用 grep
grep '"task_id":"abc-123"' data/logs/podlator.log

# 用 jq 更清爽
cat data/logs/podlator.log | jq 'select(.task_id == "abc-123")'

# 只看 ERROR 级
cat data/logs/podlator.log | jq 'select(.task_id == "abc-123" and .level == "error")'

# 按时间排序看节点流转
cat data/logs/podlator.log | jq 'select(.task_id == "abc-123") | {ts: .timestamp, node, event}'
```

**看最近的失败任务**：

```bash
cat data/logs/podlator.log | jq 'select(.event == "task_failed")' | tail -20
```

**统计某节点的平均耗时**：

```bash
cat data/logs/podlator.log \
  | jq 'select(.event == "node_completed" and .node == "transcribe") | .duration_ms' \
  | awk '{sum+=$1; n++} END {print sum/n}'
```

**找最贵的 10 次 API 调用**：

```bash
cat data/logs/podlator.log \
  | jq 'select(.cost_usd != null) | {ts: .timestamp, provider, cost_usd, task_id}' \
  | jq -s 'sort_by(-.cost_usd) | .[0:10]'
```

**算今天的总成本**：

```bash
cat data/logs/podlator.log \
  | jq 'select(.cost_usd != null and (.timestamp | startswith("2026-05-19"))) | .cost_usd' \
  | awk '{sum+=$1} END {print "Today: $" sum}'
```

### 3.3 常见问题诊断

#### 问题 1：节点卡住不动

**症状**：Web UI 显示某节点 "running" 几分钟没进展

**排查**：

```bash
# 看该任务最后 5 条日志
cat data/logs/podlator.log | jq 'select(.task_id == "xxx")' | tail -5
```

**典型原因**：
- 外部 API 超时（应该看到 `api_request` 但没看到 `api_call_completed`）→ 检查 API 商家状态、网络
- yt-dlp 下载大文件慢 → 看 audio 目录里文件大小是否在增长
- 死锁（罕见）→ 重启进程

#### 问题 2：成本超预期

**症状**：单期播客成本 > 5 元

**排查**：

```bash
# 看该任务所有 API 调用成本
cat data/logs/podlator.log \
  | jq 'select(.task_id == "xxx" and .cost_usd != null) | {node, provider, cost_usd, tokens_in, tokens_out}'
```

**典型原因**：
- 输入 token 过多 → 章节切分粒度太细，每章都喂全文给 LLM
- 重试过多 → 看 `retry_attempt` 数量
- 用了贵模型做廉价活 → 看 `polish_final` 是否被用在了不必要的地方

#### 问题 3：质量下降

**症状**：简报翻译生硬、章节切分混乱

**排查**：

1. 在 `data/logs/podlator.log` 里找该任务的 prompt（如果开了 DEBUG）
2. 跑 `tests/manual/test_prompt_quality.py`（如果有评估脚本）
3. 对比近期是否改过 prompt 模板

#### 问题 4：任务中断后无法恢复

**症状**：进程崩溃，重启后从头跑

**排查**：

```bash
# 检查 checkpoint 数据库
sqlite3 data/checkpoints.sqlite "SELECT thread_id, checkpoint_id, parent_checkpoint_id FROM checkpoints LIMIT 10;"
```

**典型原因**：
- 没用 checkpointer 启动 graph
- task_id 每次都变（应该用同一个 task_id 恢复）

---

## 4. Web UI 实时观测

### 4.1 主要页面

| 页面 | 路径 | 用途 |
|---|---|---|
| Submit | `/` | 投喂 URL |
| Queue | `/queue` | 所有任务列表 + 状态过滤 |
| TaskDetail | `/task/:id` | 单任务详情，包含：节点流程图、实时日志、成本明细、产出预览 |
| Brief | `/brief/:id` | Markdown 简报渲染 |
| Cost | `/cost` | 全局成本统计（按周/月/provider）|

### 4.2 TaskDetail 关键面板

```
┌────────────────────────────────────────────────────┐
│  任务 abc-123                          [运行中]      │
│  YouTube: "Lex Fridman & Sam Altman"               │
│  开始时间：2026-05-19 14:23  已耗时：4 分 12 秒      │
├────────────────────────────────────────────────────┤
│                                                    │
│   fetch_metadata  ✓  120ms                         │
│   download_audio  ✓  18.5s    23.4 MB              │
│   transcribe      ✓  4.5s     $0.129               │
│   diarize         ⊘  skipped                       │
│   chapter_split   ▶  running...                    │
│   summarize       ○  pending                       │
│   polish_final    ○  pending                       │
│   export_markdown ○  pending                       │
│                                                    │
├────────────────────────────────────────────────────┤
│  实时日志（自动滚动）                                │
│  14:27:34 INFO  node_started node=chapter_split    │
│  14:27:34 DEBUG api_request endpoint=deepseek/v1   │
│  ...                                               │
└────────────────────────────────────────────────────┘
```

### 4.3 实时日志过滤

Web UI 支持：

- **按级别过滤**：DEBUG / INFO / WARNING / ERROR
- **按节点过滤**：只看 transcribe 相关
- **按 event 类型过滤**：只看 api_call_failed
- **搜索**：在 message 和字段中全文搜
- **暂停滚动**：方便仔细看某条

---

## 5. 监控与告警（未来）

当前自用单机，不需要复杂监控。但代码已经为此预留：

- 日志是 JSON 格式 → 未来接 Loki / Vector / Promtail 不难
- 关键指标已经在日志中（cost、duration、tokens） → 未来接 Prometheus exporter 可解析
- 任务状态在 SQLite 中 → 未来加 webhook / 邮件告警很简单

如果未来你想加：

- **失败告警**：定时 cron 跑脚本，统计最近 1 小时的 task_failed 数量，超过阈值发邮件
- **成本告警**：单期成本超 5 元、单日总成本超 20 元发通知
- **质量告警**：抽样调评估脚本，分数下降发警

---

## 6. 调试技巧

### 6.1 让日志更详细

临时把级别降到 DEBUG：

```bash
LOG_LEVEL=DEBUG uv run podlator run "https://..."
```

会看到所有 API 请求 payload、prompt 全文等细节。

### 6.2 让日志只输出某个模块

```bash
# 只看 transcribe 节点
uv run podlator run "..." 2>&1 | grep "podlator.node.transcribe"
```

### 6.3 跳过某个节点（开发期）

在 `builder.py` 临时短路：

```python
# 临时跳过 polish_final
workflow.add_edge("summarize_chapters", "export_markdown")
# workflow.add_edge("summarize_chapters", "polish_final")
# workflow.add_edge("polish_final", "export_markdown")
```

记得改回来再提交。

### 6.4 用 fixture 重放问题

如果发现某期播客出 bug，把它的 state 序列化到 `tests/fixtures/`，然后写测试重放：

```python
def test_regression_episode_xyz(monkeypatch):
    """重放出问题的 state，确认 bug 已修。"""
    state = load_fixture("problematic_state.json")
    result = await run(state)
    assert result["...."] == ...
```

### 6.5 看 LangGraph 状态机的执行图

```python
# 调试脚本
from podlator.graph.builder import build_graph_only
graph = build_graph_only().compile()
print(graph.get_graph().draw_ascii())
```

---

## 7. 日志最佳实践（写日志时参考）

### 7.1 命名

- **event** 用动词过去时或现在时短语：`node_started`、`api_call_completed`、`fallback_triggered`
- **字段名** 用 snake_case：`task_id`、`duration_ms`、`cost_usd`
- 不要把信息塞进字符串：~`logger.info(f"Cost: ${cost}")`~ → `logger.info("api_call_completed", cost_usd=cost)`

### 7.2 数量

- 节点开始 1 条 + 结束 1 条
- 每次外部 API 调用 1 条（成功）或 2 条（失败：调用 + 错误）
- 关键中间状态可以加 1-2 条 DEBUG
- **不要在循环里 log 每次迭代**——改为循环结束后总结一条

### 7.3 内容

✅ 好的日志：

```python
log.info(
    "summarize_chapter_completed",
    chapter_index=3,
    input_tokens=2300,
    output_tokens=450,
    cost_usd=0.0023,
    duration_ms=1820,
)
```

❌ 坏的日志：

```python
log.info(f"Done chapter {i}, took some time")  # 字符串塞信息
log.info("ok")                                  # 信息量为零
log.info("...")                                 # 让人看了想骂人
```

### 7.4 错误日志

错误日志必须包含**修复线索**：

```python
log.error(
    "deepgram_api_failed",
    status_code=429,
    error_msg="rate limit exceeded",
    retry_after_seconds=60,    # ← 这是可操作信息
    retryable=True,
)
```

而不是：

```python
log.error("something went wrong")
```

---

## 8. 排查 Cheatsheet（贴墙上的版本）

```
# 我现在要排查任务 abc-123

## 1. 看节点流转
cat data/logs/podlator.log | jq 'select(.task_id=="abc-123") | {ts: .timestamp, node, event, level}'

## 2. 看错误
cat data/logs/podlator.log | jq 'select(.task_id=="abc-123" and .level=="error")'

## 3. 看成本
cat data/logs/podlator.log | jq 'select(.task_id=="abc-123" and .cost_usd!=null) | {node, provider, cost_usd}'

## 4. 看耗时
cat data/logs/podlator.log | jq 'select(.task_id=="abc-123" and .duration_ms!=null) | {node, duration_ms}'

## 5. 看 API 失败
cat data/logs/podlator.log | jq 'select(.task_id=="abc-123" and .event=="api_call_failed")'

## 6. 看是否触发降级
cat data/logs/podlator.log | jq 'select(.task_id=="abc-123" and .event=="fallback_triggered")'
```
