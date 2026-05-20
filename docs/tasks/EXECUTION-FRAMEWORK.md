# 任务执行框架

> **本文件定义所有任务计划书的通用协议。** 执行 AI 在开始任何任务前必须先读本文件。

---

## 1. 角色分工

| 角色 | 是谁 | 职责 |
|---|---|---|
| **规划者** | Claude（写任务计划书的那个） | 分析现状、设计方案、写执行计划、审核完成报告 |
| **执行者** | AI CLI（Claude Code / Cursor / 其他） | 按任务计划书逐步编码、测试、产出完成报告 |
| **用户** | 人类 | 准备资源（API Key、测试数据）、监控进度、审核关键产出 |

**核心原则**：执行者不需要做设计决策，计划书中已包含所有决策。遇到计划书未覆盖的情况，停下来说明问题，不要猜测。

---

## 2. 任务计划书结构

每份任务计划书（如 `M1.1-providers.md`）遵循统一结构：

```
# M<里程碑>.<子任务> — <标题>

## 前置条件
（上一个任务必须完成、需要哪些资源）

## 预检命令
（执行前先跑这些，确认环境正常）

## Phase 1: <名称>
### 1.1 <步骤>
### 1.2 <步骤>
### Phase 1 验证
（本 Phase 结束后必须通过的命令）

## Phase 2: ...

## 最终验证
（全部完成后的综合检查）

## 完成报告
（按模板输出）
```

---

## 3. 预检协议

**每次开始新任务前，执行者必须运行以下预检命令并确认全部通过：**

```bash
# 1. 依赖完整
uv sync

# 2. 现有测试不能挂
uv run pytest -x -q

# 3. 代码质量
uv run ruff check .
uv run ruff format --check .
uv run mypy src/

# 4. Git 状态干净
git status --short
```

**预检失败 → 停止。** 不要在一个已经有问题的代码库上继续开发。先修复问题或报告给用户。

---

## 4. 编码规范（执行者必读）

### 4.1 强制规范

以下规范不可违反，完整细节见 `CLAUDE.md`：

- **类型注解**：所有函数参数和返回值必须有类型注解
- **日志**：使用 `structlog`（`from podlator.logging import get_logger`），绝不用 `print()`
- **节点日志**：节点内用 `node_logger(state, "node_name")`，按 CLAUDE.md 第 7.3 节的必填字段
- **异常处理**：每个 `try/except` 必须 log，绝不静默吞异常
- **外部 API 日志**：必带 `provider`、`duration_ms`、`cost_usd` 字段
- **测试**：每个新增的 public 函数都必须有测试
- **导入**：每个文件首行 `from __future__ import annotations`

### 4.2 新增 Provider 的标准步骤

参考 CLAUDE.md 第 5 章：
1. 在对应目录新建 `<vendor>.py`
2. 继承基类，实现所有抽象方法
3. 在 `__init__.py` 中注册导出
4. 在 `tests/unit/providers/` 添加单元测试（mock HTTP）
5. 在 `tests/smoke/` 添加 smoke 测试（真实 API）
6. 更新 `.env.example` 如有新配置项

### 4.3 新增节点实现的标准步骤

参考 CLAUDE.md 第 4 章：
1. 保持 `@node("name")` 装饰器和 `node_logger`
2. 实现真实逻辑替换 `return {}`
3. 返回正确的 state patch（参考 `docs/ARCHITECTURE.md` 第 2 节的映射表）
4. 更新 `tests/unit/graph/nodes/test_<name>.py`：
   - 正常路径测试（mock Provider，验证返回正确字段）
   - 失败路径测试（Provider 抛异常，验证 NodeError）
   - 至少 1 个边界测试（空输入、异常数据等）

---

## 5. 验证协议

### 5.1 Phase 级验证

每个 Phase 结束后必须运行验证命令。**验证不通过 → 修复后重新验证 → 不要进入下一个 Phase。**

### 5.2 任务级最终验证

任务全部完成后，运行完整验证套件：

```bash
# 完整测试（不含 smoke）
uv run pytest -v --tb=short 2>&1 | tail -30

# 覆盖率
uv run pytest --cov --cov-report=term-missing --cov-fail-under=70 2>&1 | tail -20

# 代码质量
uv run ruff check .
uv run ruff format --check .
uv run mypy src/

# Smoke 测试（如有，且 API Key 已配置）
PODLATOR_RUN_SMOKE=1 uv run pytest tests/smoke/ -v --tb=short 2>&1 | tail -20
```

### 5.3 回归保护

**核心原则：新代码不能破坏旧测试。**

如果改动导致旧测试失败：
- 先理解为什么失败（是 bug 还是预期的接口变更）
- 如果是接口变更，同步更新测试
- 如果是 bug，修复代码，不要改测试让它"通过"

---

## 6. 完成报告格式

**每个任务完成后，执行者必须在最后输出以下格式的报告：**

````markdown
# M<x>.<y> 完成报告

## 执行摘要
- **任务**: <一句话描述>
- **状态**: ✅ 完成 / ⚠️ 部分完成（说明原因）/ ❌ 失败（说明原因）
- **新增文件数**: N 个
- **修改文件数**: N 个
- **新增测试数**: N 个

## 文件变更清单

| 文件 | 操作 | 说明 |
|---|---|---|
| `src/podlator/providers/stt/deepgram.py` | 新增 | Deepgram STT Provider 实现 |
| `src/podlator/graph/nodes/transcribe.py` | 修改 | 从占位改为真实实现 |
| ... | ... | ... |

## 测试结果

```
（粘贴 uv run pytest -v --tb=short 的完整输出）
```

### 测试统计
- 通过: XX
- 失败: 0
- 跳过: X（列出原因）

## 覆盖率

```
（粘贴 uv run pytest --cov --cov-report=term-missing 的输出）
```

### 覆盖率统计
- 整体: XX%
- 新增代码: XX%
- 核心节点(graph/nodes): XX%

## 代码质量

```
（粘贴 ruff check + mypy 输出）
```

## Smoke 测试结果（如适用）

| 测试 | 结果 | 耗时 | 费用 |
|---|---|---|---|
| test_deepgram_real | ✅ | 2.3s | $0.002 |
| ... | ... | ... | ... |

## 已知问题

（如果一切正常写"无"。否则列出每个问题及其影响。）

## DoD 自检

### 代码质量
- [x] 类型注解齐全
- [x] ruff check 通过
- [x] ruff format 通过
- [x] mypy 通过

### 测试
- [x] 新增 N 个单元测试
- [x] 失败场景已覆盖
- [x] 边界条件已覆盖
- [x] pytest 全绿
- [x] 覆盖率 >= 70%

### 日志
- [x] 节点入口/出口日志齐全
- [x] API 调用日志带 cost_usd 和 duration_ms
- [x] 无 try/except 静默吞异常

### 文档
- [x] CHANGELOG.md 已更新
````

---

## 7. 错误处理协议

### 依赖安装失败

```
→ 检查 pyproject.toml 中的包名和版本约束
→ 尝试 `uv pip install <package> --verbose` 查看具体错误
→ Apple Silicon 兼容性问题：用 `--no-binary :all:` 或暂时注释该依赖
→ 如果解决不了，在完成报告中明确记录，状态标 ⚠️
```

### 测试失败

```
→ 先看失败信息，理解是自己的 bug 还是环境问题
→ 修复 bug，不要通过修改断言来"通过"测试
→ 如果是 flaky 测试（偶尔失败），找到根因，不要用 @pytest.mark.flaky
→ 运行 3 次确认稳定通过
```

### 真实 API 调用失败（Smoke 测试）

```
→ 检查 API Key 是否在 .env 中正确配置
→ 检查 base_url 是否正确
→ 检查网络连接
→ 如果是 rate limit (429)：等 60 秒重试
→ 如果是 auth error (401/403)：API Key 可能过期，报告给用户
→ Smoke 测试失败不阻塞任务完成（标 ⚠️），但单元测试必须全绿
```

### 覆盖率不达标

```
→ 检查哪些行没覆盖（看 --cov-report=term-missing 的 Missing 列）
→ 补充测试用例（优先覆盖 error handling 路径）
→ 纯配置代码（如 __repr__）可加 # pragma: no cover
→ 不要为了凑覆盖率写无意义的测试
```

---

## 8. Git 提交协议

每个任务完成后提交一次，使用约定式提交：

```
feat(<scope>): <一句话描述>

- <要点 1>
- <要点 2>
- <要点 3>

Co-Authored-By: Claude <noreply@anthropic.com>
```

scope 参考：`graph`, `providers`, `stt`, `llm`, `api`, `web`, `storage`, `test`, `docs`

**不要在中途随意提交。** 一个任务 = 一次提交（除非任务明确分了多个提交点）。

---

## 9. 重要提醒

1. **不要跳步**：Phase 1 验证不通过就不要做 Phase 2
2. **不要猜测**：遇到计划书没覆盖的设计决策，停下来说明
3. **不要静默修改接口**：如果需要改 Provider 接口或 State 字段，必须在完成报告中明确记录
4. **测试先行**：尽量先写测试再写实现（TDD），至少同步写
5. **日志不是可选的**：每个 API 调用必须有结构化日志
6. **保持小步验证**：宁可多跑几次 pytest，不要写完一大坨再测
