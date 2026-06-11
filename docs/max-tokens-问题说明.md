# max_tokens 配置问题说明

## 一句话版

项目里 DeepSeek 的 `max_tokens` 配成了 8192，但 DeepSeek V4-Flash 实际支持到 **384K**。结果是说话人分离时 LLM 输出被截断，JSON 写到一半就断了。

## 上下文窗口 vs max_tokens（别搞混）

这两个东西经常被当成一回事，但其实完全不同：

| | 上下文窗口 | max_tokens |
|---|---|---|
| **是什么** | 输入 + 输出 的总容量 | 单次最多**生成**多少 |
| **类比** | 一张桌子的总面积 | 桌上能铺多大的纸 |
| **DeepSeek V4-Flash** | **1,000,000**（一百万） | **384,000** |

- 上下文 1M 意味着你可以塞一本《三体》进去让它读。
- max_tokens 384K 意味着它一次最多吐 38 万 tokens 的回复。
- 我们的配置把 max_tokens 压到了 8192，相当于明明有 A4 纸，却只让它在便利贴上写字。

## 实际问题是什么

`assign-speakers`（说话人分离）会把 380 条字幕切成 6 片，每片 80 条，调 DeepSeek 输出 JSON 标注说话人。DeepSeek 输出 JSON 的同时会在前后加 markdown 代码块和分析文字，结果超过 8192 tokens，JSON 被截断了。

现象：
```
{"index": 73, "speaker": "PAUL"},
{"index": 74, "speaker": "PA    ← 写到这里就被截断了
```

## 涉及哪些地方

| 位置 | 当前值 | 说明 |
|---|---|---|
| `config.py` 的 `DEEPSEEK_MAX_TOKENS` | 8192 | 全局默认，V3 时代的配置 |
| `assign_speakers.py` 里的 `max_tokens` | 8192（刚从 4096 改上来） | 硬编码，覆盖了全局配置 |

两个地方都远低于 V4-Flash 的真实上限 384K。

## 为什么不全拉到 384K

1. **没必要**：输出说话人 JSON 最多几千 tokens。问题不是上限不够，而是 DeepSeek 在 JSON 外面加了太多废话。更好的解法是**减小分片大小**（80→50 条），每片输出短了自然不截断。
2. **省钱**：max_tokens 只是上限，实际不会多用。但设太大万一 prompt 出 bug 让模型狂输出，就浪费了。
3. **真正值得调的**：`douyin-script` Stage 2 定稿需要 6000 字中文 ≈ 12000+ tokens 输出，如果用 DeepSeek 直接定稿（不用 Codex CLI），8192 就不够。

## 建议

- 短期：assign-speakers 的 shard_size 从 80 降到 50，比拉高 max_tokens 更治本
- 长期：`DEEPSEEK_MAX_TOKENS` 默认值更新到 V4-Flash 的真实上限或一个合理的中间值（如 32K）

## 已纳入 M5 规划（2026-06）

复盘代码后发现这其实是「静默截断」这一种病在**三个边界**上发作，不止本文说的说话人这一处：

| 边界 | 病灶 | 归属 |
|---|---|---|
| A 输出·说话人 | `assign_speakers.py` 分片 JSON 被 8192 截断 → 整片丢标签 | **M5.0** |
| B 输出·定稿 | `douyin_script.py` 的 `_complete_with_fallback` 调 finalize **根本没传 max_tokens**，降级到 API 即腰斩 | **M5.4** |
| C 输入·正文 | `DEFAULT_MAX_INPUT_CHARS=36000` 静默丢 40–75% 正文 | **M5.2** |

三处共同病根是**没人读 `finish_reason`**。解决方案不再是「只调一个数」，而是：

1. provider 层统一读 `finish_reason`，截断即 `log.warning`（M5.0，三处共享的检测地基）。
2. 本文 A 边界 = M5.0：分片 80→50 + **截断时正则抢救已完成的 JSON**（73 条完整就救回 73，不再整片丢）+ 默认值 8192→32K。
3. B、C 边界分别在 M5.4 / M5.2 复用同一套检测；M5.1 的 lint 再加一个「结尾未落终止符」的永久跳闸器，让截断稿再也无法静默通过。

详见 `docs/tasks/M5.0-truncation-hardening.md`（✅ 已执行）与 `docs/tasks/M5-overview.md` 第 1 节「横切病症」。

## 执行状态

M5.0 已落地（2026-06-11）：
- 分片 80→50 + 部分 JSON 抢救 + finish_reason 检测 + 默认值 32K。
- B、C 边界分别由 M5.4 / M5.2 接手。
- M5.1 lint 的截断探针 = 永久跳闸器，让截断稿再也无法静默通过。
