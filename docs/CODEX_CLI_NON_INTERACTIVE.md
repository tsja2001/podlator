# Codex CLI 非交互式调用指南

本文记录 Podlator 中使用 Codex CLI 做强模型定稿、润色和联网补充背景时的推荐调用方式。

当前本机验证版本：

```bash
codex-cli 0.133.0-alpha.1
```

## 核心入口

Codex 的非交互式入口是：

```bash
codex exec [OPTIONS] [PROMPT]
```

最小调用：

```bash
codex exec "把下面这段中文口播稿润色得更自然，但不要改变事实。"
```

更推荐在自动化里用 stdin 传入长 prompt，避免 shell 转义和命令长度问题：

```bash
cat prompt.md | codex exec -
```

如果同时传了位置参数和 stdin，Codex 会把 stdin 追加为 `<stdin>` 内容块。Podlator 的 `codex_cli` provider 当前使用 stdin 传 prompt。

## Podlator 当前用法

项目里的实现位置：

```text
src/podlator/providers/llm/cli_tool.py
```

当前 `codex_cli` 实际等价于：

```bash
codex exec \
  --cd "$TMP_DIR" \
  --skip-git-repo-check \
  --sandbox read-only \
  --ephemeral \
  -o "$TMP_DIR/output.txt"
```

然后把合并后的 `system + user prompt` 通过 stdin 传入。

这里几个参数的含义：

| 参数 | 作用 | Podlator 为什么用 |
|---|---|---|
| `exec` | 非交互式执行 | 适合 pipeline 自动调用 |
| `--cd "$TMP_DIR"` | 指定工作目录 | 用空临时目录隔离项目上下文，避免 `CLAUDE.md` / `AGENTS.md` 污染成稿 prompt |
| `--skip-git-repo-check` | 允许在非 Git 目录运行 | 临时目录不是仓库 |
| `--sandbox read-only` | 禁止模型写工作区文件 | 定稿只需要返回文本 |
| `--ephemeral` | 不保存 session 文件 | 避免批处理生成大量会话记录 |
| `-o FILE` / `--output-last-message FILE` | 把最后回复写入文件 | 方便 Python 子进程稳定读取结果 |

在 Podlator 里启用：

```bash
# .env
LLM_PROVIDER_SUMMARIZE=deepseek
LLM_PROVIDER_POLISH=codex_cli
CLI_TOOL_CODEX_MODEL=
CLI_TOOL_TIMEOUT_S=600
```

`CLI_TOOL_CODEX_MODEL` 留空时使用 Codex CLI 默认模型；如果要指定模型：

```bash
CLI_TOOL_CODEX_MODEL=gpt-5
```

命令行也可以临时指定 Stage2 定稿 provider：

```bash
uv run podlator douyin-script transcript.speakers.json \
  -o "抖音解说稿.md" \
  --title "Episode Title" \
  --finalize-provider codex_cli
```

或一键流程：

```bash
uv run podlator pipeline-douyin "episode.srt" \
  -o "抖音解说稿.md" \
  --title "Episode Title" \
  --finalize-provider codex_cli
```

## 联网搜索

Codex CLI 的联网搜索开关是顶层全局参数，必须放在 `exec` 前面：

```bash
--search
```

示例：

```bash
cat prompt.md | codex --search exec \
  --sandbox read-only \
  --ephemeral \
  -o result.md \
  -
```

适合 Podlator 的场景：

| 场景 | 是否建议联网 | 说明 |
|---|---:|---|
| 科技人物背景补充 | 建议 | 例如人物职位、公司近况、论文/产品最新进展 |
| 播客标题/简介生成 | 可选 | 需要核对节目、嘉宾、机构背景时开启 |
| 纯口语润色 | 不建议 | 没有外部事实需求，联网会变慢且增加不确定性 |
| 事实敏感定稿 | 建议 | prompt 里要求“联网核对事实，只补充能确认的信息” |

注意：项目当前 `codex_cli` provider 还没有配置项来自动追加 `--search`。如果要把联网作为 pipeline 能力接入，可以新增类似：

```text
CLI_TOOL_CODEX_SEARCH_ENABLED=true
```

然后在 `cli_tool.py` 的 Codex 命令中追加 `--search`。

## 常用参数速查

### 模型

```bash
codex exec -m gpt-5 "润色这段稿子"
```

Podlator 中对应：

```bash
CLI_TOOL_CODEX_MODEL=gpt-5
```

### 工作目录

```bash
codex exec --cd /path/to/workdir "阅读这个目录里的文件并总结"
```

对 Podlator 来说有两种策略：

| 策略 | 命令 | 用途 |
|---|---|---|
| 隔离上下文 | `--cd "$TMP_DIR"` | 当前默认。只让模型处理 prompt，不读取项目文件 |
| 允许读项目 | `--cd "$PODLATOR_DIR"` | 让模型参考 README、prompt、样稿等项目上下文 |

如果只是最终定稿，优先用临时目录。只有明确需要模型读项目文件时才切到项目目录。

### 沙箱

```bash
codex exec --sandbox read-only "只阅读并分析"
codex exec --sandbox workspace-write "可以修改当前工作区"
codex exec --sandbox danger-full-access "完全放开文件系统限制"
```

Podlator 自动化定稿推荐：

```bash
--sandbox read-only
```

如果让 Codex 直接改稿件文件，可以用：

```bash
codex exec \
  --cd "/path/to/episode" \
  --sandbox workspace-write \
  "请直接修改 抖音解说稿.md，提升口语自然度，不改变事实。"
```

### 审批策略

```bash
codex -a never exec "执行任务"
```

`exec` 自动化里常用 `never`，表示不等待人工审批；失败就直接返回给模型处理。当前 Podlator 没显式传 `-a never`，因为 `read-only` 定稿不需要执行危险命令。

### 输出到文件

```bash
codex exec -o result.md "输出最终稿，不要解释过程。"
```

自动化里优先用 `-o`，不要只解析 stdout。stdout 可能包含运行事件、日志或 JSONL。

### JSONL 事件流

```bash
codex exec --json "完成任务"
```

适合调试、观察模型中间事件；不适合直接作为最终稿读取。最终文本仍建议用 `-o`。

### 结构化输出

```bash
codex exec \
  --output-schema schema.json \
  -o result.json \
  "按 schema 输出播客标题、简介和开场白。"
```

适合把“标题 / 简介 / 开场白 / 标签”这类内容做成可机器读取的 JSON。

### 图片输入

```bash
codex exec \
  -i cover.png \
  "根据封面图和节目主题，给出 5 个中文标题方向。"
```

适合做封面图文案、视觉风格分析等，但当前 Podlator 主流程暂时用不到。

### 忽略配置和规则

```bash
codex exec --ignore-user-config --ignore-rules "只按本 prompt 执行"
```

如果要最大限度保证输出只受当前 prompt 控制，可以加这两个参数。但通常 `--cd "$TMP_DIR"` 已经能避开项目规则文件。

## 针对 Podlator 的推荐命令模板

### 1. 纯润色，不联网

```bash
cat final_prompt.md | codex exec \
  --cd "$(mktemp -d)" \
  --skip-git-repo-check \
  --sandbox read-only \
  --ephemeral \
  -o polished.md \
  -
```

用途：口播稿自然化、节奏调整、去 AI 腔。

### 2. 联网补充背景后定稿

```bash
cat final_prompt.md | codex --search exec \
  --cd "$(mktemp -d)" \
  --skip-git-repo-check \
  --sandbox read-only \
  --ephemeral \
  -o polished.md \
  -
```

prompt 建议明确写：

```text
只联网核对人物、机构、产品、论文、时间线等事实。
不要把未经确认的信息写成确定事实。
最终只输出中文口播稿正文，不要输出搜索过程。
```

### 3. 生成播客 meta JSON

`schema.json` 示例：

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["title", "description", "opening"],
  "properties": {
    "title": { "type": "string" },
    "description": { "type": "string" },
    "opening": { "type": "string" }
  }
}
```

调用：

```bash
cat meta_prompt.md | codex --search exec \
  --sandbox read-only \
  --ephemeral \
  --output-schema schema.json \
  -o podcast_meta.json \
  -
```

### 4. 让 Codex 直接改本地稿件

```bash
codex exec \
  --cd "/Users/yangzhuoran/program/podlator/project/某一期/抖音剪辑版" \
  --sandbox workspace-write \
  "请修改 抖音解说稿.md：保留事实和结构，提升中文口语节奏，删掉重复表达。"
```

这个方式适合人工批处理，不建议直接接进 Podlator pipeline。pipeline 更适合“输入 prompt，读取 `-o` 结果，再由 Python 写目标文件”。

## 和 Claude CLI 的差异

Podlator 当前同时支持：

| Provider | 底层命令 | Prompt 传入 | 结果读取 | 适合场景 |
|---|---|---|---|---|
| `claude_cli` | `claude -p` | 命令参数 | stdout JSON 的 `result` | Claude Code 会员定稿 |
| `codex_cli` | `codex exec` | stdin | `-o` 输出文件 | ChatGPT 会员定稿、可选联网搜索 |

Codex CLI 没有单独的 `--system-prompt` 参数。项目里会把 system prompt 和 user prompt 合并成一个文本：

```text
{system}

---

{user prompt}
```

因此写 Codex prompt 时，要把角色、约束、输出格式都放在同一份 prompt 里。

## 接入建议

短期建议：

- 保持当前 `codex_cli` 默认不联网，服务于稳定定稿。
- 需要事实补充时，手动用 `codex --search exec` 跑一次独立润色或 meta 生成。
- 如果联网定稿变成高频需求，再给 `CLIToolProvider` 增加 `CLI_TOOL_CODEX_SEARCH_ENABLED`。

长期可以拆成两个 provider：

| Provider | 建议用途 |
|---|---|
| `codex_cli` | 不联网，稳定定稿 |
| `codex_search_cli` | 联网核事实、补背景、生成 meta |

这样 pipeline 里可以明确区分“语言润色”和“事实增强”，日志和失败降级也更清楚。
