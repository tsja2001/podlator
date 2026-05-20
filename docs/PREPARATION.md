# 前置准备清单

> **给人类看的文档。** 在让 AI 执行 M0 之前，逐项完成以下准备。
> 预计耗时：30-60 分钟（主要等 API 审批）。

---

## 1. 环境工具

逐条运行以下命令，确认输出正常：

```bash
python3 --version    # >= 3.12（必须）
uv --version         # 任意版本即可
node --version       # >= 20
pnpm --version       # 任意版本即可
ffmpeg -version      # 任意版本即可
git --version        # 任意版本即可
```

### 缺失时的安装命令（macOS）

```bash
# Python 3.12+（如果 brew 默认版本低于 3.12）
brew install python@3.12

# uv（Python 包管理）
curl -LsSf https://astral.sh/uv/install.sh | sh

# Node.js 20+
brew install node@20

# pnpm
npm install -g pnpm

# ffmpeg（音频处理）
brew install ffmpeg
```

---

## 2. API Keys

> M0 阶段全部用 mock，**不调用任何真实 API**。但建议提前注册，以免阻塞 M1。
> 如果你想先跳过，直接进入 M0 没问题——只需把 .env 里的 key 留空即可。

### 2.1 Deepgram — STT 转写

- **官网**: https://console.deepgram.com/signup
- **注册**: 支持 Google / GitHub 一键登录
- **免费额度**: 新账号有 **$200 免费**，足够开发期使用
- **获取 Key**:
  1. 登录后进入左侧 Settings → API Keys
  2. 点 "Create a New API Key"
  3. 名称随意（如 `podlator-dev`），权限选 Member
  4. 复制 Key → 填入 `.env` 的 `DEEPGRAM_API_KEY=`

### 2.2 DeepSeek — 章节切分 + 翻译 LLM

- **官网**: https://platform.deepseek.com/sign_up
- **注册**: 手机号注册
- **费用**: 需充值，最低 ¥10（建议 ¥50，足够跑几十期播客）
- **获取 Key**:
  1. 登录后点左上角头像 → API Keys
  2. 点 "创建 API Key"
  3. 复制 Key → 填入 `.env` 的 `DEEPSEEK_API_KEY=`
- **注意**: DeepSeek 使用 OpenAI 兼容 API，base_url 为 `https://api.deepseek.com`

### 2.3 Claude — 全局润色 LLM（第三方平台）

本项目通过第三方平台以 OpenAI 兼容 API 调用 Claude，不直接使用 Anthropic 官方 API。

- **获取 Key**: 从你使用的第三方平台获取 API Key
- **填入 `.env`**:
  - `CLAUDE_API_KEY=` — 平台提供的 API Key
  - `CLAUDE_BASE_URL=https://api.b.ai/v1` — 平台 API 地址（已有默认值）

### 汇总表

| 环境变量 | 服务 | 说明 | M0 是否必需 |
|---|---|---|---|
| `DEEPGRAM_API_KEY` | Deepgram Nova-3 | 新账号 $200 免费 | 否（mock） |
| `DEEPSEEK_API_KEY` | DeepSeek V4-Flash | 需充值 ¥10+ | 否（mock） |
| `CLAUDE_API_KEY` | Claude Opus 4.7 | 第三方平台 Key | 否（mock） |
| `CLAUDE_BASE_URL` | Claude API 地址 | 默认 `https://api.b.ai/v1` | 否 |

---

## 3. 测试素材

### M0 不需要真实素材

M0 的所有测试都用 mock 数据，不需要真实音频或 YouTube URL。测试 fixture 会在 M0 执行过程中自动创建。

### M1 需要的素材（提前准备可选）

如果你想提前准备，选两个英文播客/YouTube 视频 URL：

| 用途 | 建议时长 | 说明 |
|---|---|---|
| 快速 E2E 测试 | 3-10 分钟 | 用于开发期反复测试，选内容简单的 |
| 完整 pipeline 测试 | 30-60 分钟 | 用于验证完整流程，选你真正想听的 |

**推荐来源**：
- Lex Fridman Podcast clips（YouTube，英文清晰）
- TED Talks（3-18 分钟，适合短测试）
- All-In Podcast（多人对话，测说话人分离）

> 不急着选，到 M1 再定也行。

---

## 4. 验证环境就绪

完成上述准备后，运行此一键检查脚本：

```bash
echo "=== 环境检查 ===" && \
python3 -c "import sys; v=sys.version_info; assert v >= (3,12), f'需要 Python 3.12+, 当前 {v.major}.{v.minor}'; print(f'✅ Python {v.major}.{v.minor}.{v.micro}')" && \
uv --version && echo "✅ uv 已安装" && \
node --version && echo "✅ Node.js 已安装" && \
pnpm --version && echo "✅ pnpm 已安装" && \
ffmpeg -version 2>&1 | head -1 && echo "✅ ffmpeg 已安装" && \
git --version && echo "✅ Git 已安装" && \
echo "=== 全部通过，可以开始 M0 ==="
```

---

## 5. 准备完毕后

环境就绪后，将以下内容告诉 AI（Claude Code / Cursor）：

```
请按照 docs/tasks/M0-execution.md 执行 Milestone 0。
逐个 Phase 执行，每个 Phase 结束后运行验证命令。
```

AI 会按照执行手册中的 10 个 Phase 逐步完成 M0 骨架搭建。
