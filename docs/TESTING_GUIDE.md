# 测试工程指南

> 本文件给两类读者看：
> - **用户**：测试工程新手，需要从零理解 pytest 生态和测试设计思想
> - **AI IDE**：写测试时按本指南的模板和约定来

本文是教程 + 项目特定约定的结合。如果你只想看"怎么写"，跳到第 4 章；想理解"为什么这样写"，从第 1 章开始读。

---

## 1. 为什么测试，测什么

### 1.1 测试解决什么问题

写代码时，你脑子里有一个"代码应该如何工作"的模型。代码本身只是这个模型的一个实现。两者之间总有缝隙：

- 你以为 "DeepSeek 返回 JSON"，结果它返回了 markdown 代码块包裹的 JSON
- 你以为 "用户输入是 URL"，结果用户粘进来一串带空格的字符串
- 你以为 "网络一定可用"，结果 Wi-Fi 断了 5 秒

测试是把这些**"我以为"显式化**——用代码把假设固化下来，未来任何改动导致假设破裂都会立刻被发现。

### 1.2 测试的三个目的

按重要性排序：

1. **回归保护**：今天能跑的功能，明天改了别的代码后还能跑
2. **设计文档**：好的测试是最准确的"这个函数怎么用"文档（注释会过期，测试会随代码同步）
3. **设计驱动**：写测试时如果发现"这函数没法测"，说明设计有问题，重构信号

> 注意：**测试不是"为了证明代码没 bug"**。世界上没有任何方法能"证明"代码没 bug。测试只能**降低出 bug 的概率**和**让出 bug 时更快定位**。

### 1.3 测试金字塔

```
            /\
           /  \   Manual / E2E      ← 慢、贵、脆弱，少而精
          /----\
         /      \  Integration       ← 中速，验证组件协作
        /--------\
       /          \  Unit             ← 快、便宜、稳定，海量
      /____________\
```

经验法则：**单元测试 70%、集成测试 20%、端到端测试 10%**。

新手最容易犯的错：跳过单元测试直接写"一个测试跑通整个流程"，结果是：
- 跑一次几十秒，不愿意频繁跑
- 一个失败连环失败，定位困难
- 改动任何代码都得改一堆测试

---

## 2. pytest 基础（JS 开发者速通）

### 2.1 心智模型对比

| 概念 | JS 生态（Vitest/Jest） | Python（pytest） |
|---|---|---|
| 测试运行器 | `vitest` / `jest` | `pytest` |
| 测试文件命名 | `*.test.ts` / `*.spec.ts` | `test_*.py` / `*_test.py` |
| 测试函数 | `test('xxx', () => {...})` / `it(...)` | `def test_xxx(): ...` |
| setup / teardown | `beforeEach` / `afterEach` | `fixture` |
| 断言 | `expect(x).toBe(y)` | `assert x == y` |
| Mock | `vi.mock()` / `jest.mock()` | `monkeypatch` / `unittest.mock` / `pytest-mock` |
| 异步测试 | 直接 `async/await` | `pytest.mark.asyncio` + `async def` |
| 测试组 | `describe('group', ...)` | 用类 `class TestXxx:` 或目录组织 |
| 跳过 | `it.skip(...)` | `@pytest.mark.skip` / `@pytest.mark.skipif(...)` |
| 只跑一个 | `it.only(...)` | `pytest -k "name"` |
| 参数化 | `it.each([...])` | `@pytest.mark.parametrize` |
| 快照 | Vitest 内置 | `pytest --snapshot-update`（syrupy 库） |

### 2.2 第一个测试

```python
# tests/unit/test_hello.py
def test_addition_works():
    assert 1 + 1 == 2

def test_string_split():
    result = "a,b,c".split(",")
    assert result == ["a", "b", "c"]
    assert len(result) == 3
```

运行：

```bash
uv run pytest tests/unit/test_hello.py -v
```

输出：

```
tests/unit/test_hello.py::test_addition_works PASSED
tests/unit/test_hello.py::test_string_split PASSED
```

### 2.3 异步测试

```python
import pytest

@pytest.mark.asyncio   # 在 pyproject.toml 设了 asyncio_mode=auto 后可省略
async def test_async_function():
    result = await some_async_func()
    assert result == "expected"
```

我们的 `pyproject.toml` 已经设置 `asyncio_mode = "auto"`，所以**所有 `async def` 测试函数自动被识别**，不用每个都加装饰器。

### 2.4 fixture（核心概念）

fixture 是 pytest 最强大也最容易让 JS 开发者懵的概念。一句话：**fixture 是依赖注入 + setup/teardown 的混合体**。

```python
import pytest
from pathlib import Path

# 定义一个 fixture
@pytest.fixture
def sample_audio_path(tmp_path: Path) -> Path:
    """提供一个临时音频文件路径（指向 fixtures 里的样本）。"""
    return Path(__file__).parent.parent / "fixtures" / "audio" / "sample_30s.mp3"


# 使用 fixture：函数参数名 = fixture 名
def test_audio_exists(sample_audio_path: Path):
    assert sample_audio_path.exists()
    assert sample_audio_path.suffix == ".mp3"
```

**JS 类比**：
```ts
// JS 你会这样写：
let samplePath: string
beforeEach(() => { samplePath = "..." })
test('audio exists', () => { expect(fs.existsSync(samplePath)).toBe(true) })

// Python pytest 直接函数参数注入，更优雅
```

**常用内置 fixtures**：

| Fixture | 作用 |
|---|---|
| `tmp_path` | 提供一个测试专属的临时目录（自动清理） |
| `tmp_path_factory` | 跨测试共享的临时目录 |
| `monkeypatch` | 临时修改环境变量、属性、字典等 |
| `capsys` / `capfd` | 捕获 stdout/stderr |
| `caplog` | 捕获日志输出 |

### 2.5 参数化（同一个测试跑多组数据）

```python
import pytest

@pytest.mark.parametrize("input_url,expected_type", [
    ("https://www.youtube.com/watch?v=abc", "youtube"),
    ("https://example.com/podcast.rss", "rss"),
    ("https://example.com/episode.mp3", "manual"),
])
def test_detect_source_type(input_url: str, expected_type: str):
    assert detect_source_type(input_url) == expected_type
```

一次性测了 3 个用例，每个独立汇报通过/失败。比写 3 个 test 函数清爽。

### 2.6 Mock 入门

我们用 `pytest-httpx` mock HTTP，用 `monkeypatch` mock 其他。

```python
import pytest
from pytest_httpx import HTTPXMock

async def test_deepgram_provider_handles_429(httpx_mock: HTTPXMock):
    # 假装 Deepgram 返回 429
    httpx_mock.add_response(
        url="https://api.deepgram.com/v1/listen",
        status_code=429,
        json={"error": "rate_limit"},
    )
    
    provider = DeepgramSTT(api_key="fake")
    with pytest.raises(ProviderError) as exc_info:
        await provider.transcribe(Path("fake.mp3"))
    
    assert exc_info.value.status_code == 429
```

`monkeypatch` 用法：

```python
def test_uses_env_var(monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key")
    # 现在 os.getenv("DEEPGRAM_API_KEY") 返回 "test-key"
    # 测试结束后自动恢复
    ...
```

### 2.7 异常断言

```python
import pytest

def test_invalid_url_raises():
    with pytest.raises(ValueError, match="invalid url"):
        validate_url("not a url")
```

`match` 是正则，匹配异常 message 里的子串。

### 2.8 跳过 / 条件跳过

```python
import os
import pytest

@pytest.mark.skip(reason="WIP，等 M4 完成再启用")
def test_local_stt():
    ...

@pytest.mark.skipif(
    not os.getenv("PODLATOR_RUN_SMOKE"),
    reason="Smoke 测试需要真实 API key，设置 PODLATOR_RUN_SMOKE=1 启用",
)
def test_deepgram_real_api():
    ...
```

---

## 3. 测试设计思想

### 3.1 AAA 模式

每个测试遵循 **Arrange-Act-Assert** 三段式：

```python
async def test_transcribe_returns_segments_with_speakers():
    # === Arrange：准备 ===
    provider = DeepgramSTT(api_key="fake")
    audio = Path("tests/fixtures/audio/sample_30s.mp3")
    
    # === Act：执行 ===
    result = await provider.transcribe(audio)
    
    # === Assert：断言 ===
    assert len(result.segments) > 0
    assert all(s.get("speaker") for s in result.segments)
    assert result.provider == "deepgram"
```

用空行明确区分三段。**好的测试一眼能看出"准备了什么、做了什么、期望什么"**。

### 3.2 一个测试 = 一个行为

❌ 反模式：

```python
def test_transcribe():
    # 测了成功
    result = transcribe(audio)
    assert result.text
    
    # 顺便测了失败
    with pytest.raises(Exception):
        transcribe(None)
    
    # 顺便测了缓存
    result2 = transcribe(audio)
    assert result == result2
```

✅ 正确：

```python
def test_transcribe_succeeds_with_valid_audio(): ...
def test_transcribe_raises_when_audio_is_none(): ...
def test_transcribe_returns_cached_result_for_same_audio(): ...
```

**为什么**：一个失败一个原因。如果第一种写法挂在第三个断言，你不会知道前两个其实是好的（除非看输出，但失败信息会很混乱）。

### 3.3 测试命名

命名格式：`test_<被测对象>_<行为>_<条件>`

好例子：
- `test_transcribe_falls_back_to_local_when_deepgram_returns_429`
- `test_chapter_split_returns_single_chapter_when_audio_under_5_min`
- `test_download_raises_when_url_is_unreachable`

坏例子：
- `test_transcribe`（测什么？）
- `test_works`（什么 works？）
- `test_case_1`（毫无信息）

**测试名读起来就像规格说明书**。

### 3.4 边界条件清单

每个公共函数，问自己：

- 空输入：`""`, `[]`, `None`, `{}`
- 超长输入：100k 字符的字符串
- 边界值：0、负数、正好等于阈值
- 重复调用：调两次结果一样吗
- 并发：多个调用同时进来会撞吗
- 非法输入：错误类型、错误格式
- 外部失败：API 5xx、超时、断网

不一定每个都测，但**每个都问一遍**，决定哪些值得测。

### 3.5 Test Doubles 谱系

新手常把"mock"当成所有"假对象"的统称，其实有细分：

| 类型 | 用途 | 例子 |
|---|---|---|
| **Dummy** | 占位，不被实际使用 | 函数签名要 logger 但测试不验证日志 |
| **Stub** | 返回预设值 | 假装 API 返回固定 JSON |
| **Fake** | 真实但简化的实现 | 内存数据库代替真 DB |
| **Spy** | 记录调用但行为真实 | 包一层记录"被调过几次" |
| **Mock** | 验证交互（断言被怎么调） | 验证 `logger.error` 被调用了 |

**我们项目偏好顺序**：Fake > Stub > Mock。

- 优先用 **Fake**（如内存版 DB）：测试真实代码路径，最稳
- 其次用 **Stub**（如 `httpx_mock`）：边界清晰
- **Mock 慎用**：mock 容易和实现耦合，重构时一改全坏

### 3.6 测试覆盖率的陷阱

覆盖率高 ≠ 测试好。这段代码 100% 覆盖也可能错：

```python
def add(a, b):
    return a + b

def test_add():
    add(1, 2)   # 覆盖率 100%，但没断言！
```

**真正重要的是断言密度和场景覆盖**。把覆盖率当**最低门槛**而不是目标。

---

## 4. Podlator 项目测试模板

### 4.1 节点测试模板

```python
"""Tests for podlator.graph.nodes.transcribe."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from podlator.errors import NodeError
from podlator.graph.nodes.transcribe import run
from podlator.graph.state import PodlatorState
from podlator.providers.stt.base import STTResult


@pytest.fixture
def base_state(tmp_path: Path) -> PodlatorState:
    """提供一个最小可用 state，节点测试都基于它派生。"""
    audio = tmp_path / "test.mp3"
    audio.write_bytes(b"fake audio bytes")
    return {
        "task_id": "test-task-001",
        "source_url": "https://example.com/episode.mp3",
        "source_type": "manual",
        "status": "running",
        "started_at": datetime.now(),
        "completed_at": None,
        "current_node": None,
        "audio_path": audio,
        "audio_format": "mp3",
        "cost_breakdown": {},
        "node_durations_ms": {},
        "errors": [],
    }


@pytest.fixture
def mock_stt_provider(monkeypatch):
    """把 get_stt_provider 工厂替换成 mock，返回预设 STT 结果。"""
    mock_provider = AsyncMock()
    mock_provider.name = "deepgram"
    mock_provider.transcribe = AsyncMock(
        return_value=STTResult(
            full_text="Hello world",
            segments=[
                {"start": 0.0, "end": 2.0, "text": "Hello", "speaker": "speaker_0"},
                {"start": 2.0, "end": 4.0, "text": "world", "speaker": "speaker_1"},
            ],
            speakers={},
            duration_seconds=4.0,
            cost_usd=0.001,
            provider="deepgram",
        )
    )
    monkeypatch.setattr(
        "podlator.graph.nodes.transcribe.get_stt_provider",
        lambda name: mock_provider,
    )
    return mock_provider


# === 正常路径 ===

async def test_transcribe_returns_segments_with_speakers(
    base_state: PodlatorState, mock_stt_provider
):
    result = await run(base_state)

    assert result["transcript_raw"] == "Hello world"
    assert len(result["transcript_segments"]) == 2
    assert result["transcript_segments"][0]["speaker"] == "speaker_0"
    assert result["stt_provider"] == "deepgram"


async def test_transcribe_records_cost_in_breakdown(
    base_state: PodlatorState, mock_stt_provider
):
    result = await run(base_state)
    assert result["cost_breakdown"]["transcribe"] == pytest.approx(0.001)


# === 失败路径 ===

async def test_transcribe_raises_node_error_when_provider_fails(
    base_state: PodlatorState, monkeypatch
):
    failing_provider = AsyncMock()
    failing_provider.transcribe = AsyncMock(side_effect=RuntimeError("API down"))
    monkeypatch.setattr(
        "podlator.graph.nodes.transcribe.get_stt_provider",
        lambda name: failing_provider,
    )

    with pytest.raises(NodeError) as exc_info:
        await run(base_state)

    assert exc_info.value.node == "transcribe"


# === 边界条件 ===

async def test_transcribe_raises_when_audio_path_missing(
    base_state: PodlatorState, mock_stt_provider
):
    base_state["audio_path"] = None
    with pytest.raises(NodeError):
        await run(base_state)
```

**关键点**：
- 用 fixture 提供 `base_state`，每个测试在它基础上微调
- mock 停在"系统边界"（STT provider），不 mock 自己的逻辑
- 三个测试分别覆盖：正常 / 失败 / 边界
- 测试名能直接当文档读

### 4.2 Provider 测试模板

```python
"""Tests for podlator.providers.stt.deepgram."""
from __future__ import annotations

from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from podlator.errors import ProviderError
from podlator.providers.stt.deepgram import DeepgramSTT


@pytest.fixture
def sample_audio(tmp_path: Path) -> Path:
    audio = tmp_path / "test.mp3"
    audio.write_bytes(b"fake audio bytes")
    return audio


@pytest.fixture
def deepgram_success_response() -> dict:
    """Deepgram 成功响应的最小样本（脱敏版）。"""
    return {
        "results": {
            "channels": [{
                "alternatives": [{
                    "transcript": "Hello world",
                    "words": [
                        {"word": "Hello", "start": 0.0, "end": 0.5, "speaker": 0},
                        {"word": "world", "start": 0.5, "end": 1.0, "speaker": 1},
                    ],
                }]
            }],
            "utterances": [
                {"speaker": 0, "transcript": "Hello", "start": 0.0, "end": 0.5},
                {"speaker": 1, "transcript": "world", "start": 0.5, "end": 1.0},
            ],
        },
        "metadata": {"duration": 1.0},
    }


# === 正常路径 ===

async def test_transcribe_parses_response_correctly(
    httpx_mock: HTTPXMock,
    sample_audio: Path,
    deepgram_success_response: dict,
):
    httpx_mock.add_response(
        url__startswith="https://api.deepgram.com",
        json=deepgram_success_response,
    )

    provider = DeepgramSTT(api_key="test")
    result = await provider.transcribe(sample_audio)

    assert result.full_text == "Hello world"
    assert len(result.segments) == 2
    assert result.duration_seconds == 1.0


# === 失败路径：参数化测多个 HTTP 错误码 ===

@pytest.mark.parametrize("status_code,error_substring", [
    (401, "unauthorized"),
    (429, "rate limit"),
    (500, "server error"),
])
async def test_transcribe_raises_on_http_errors(
    httpx_mock: HTTPXMock,
    sample_audio: Path,
    status_code: int,
    error_substring: str,
):
    httpx_mock.add_response(
        url__startswith="https://api.deepgram.com",
        status_code=status_code,
        json={"error": f"some {error_substring} error"},
    )

    provider = DeepgramSTT(api_key="test")
    with pytest.raises(ProviderError) as exc_info:
        await provider.transcribe(sample_audio)

    assert exc_info.value.status_code == status_code


# === 失败路径：超时 ===

async def test_transcribe_raises_on_timeout(
    httpx_mock: HTTPXMock,
    sample_audio: Path,
):
    import httpx
    httpx_mock.add_exception(httpx.TimeoutException("timed out"))

    provider = DeepgramSTT(api_key="test")
    with pytest.raises(ProviderError, match="timeout"):
        await provider.transcribe(sample_audio)


# === 边界：文件不存在 ===

async def test_transcribe_raises_when_audio_file_missing(tmp_path: Path):
    nonexistent = tmp_path / "does_not_exist.mp3"
    provider = DeepgramSTT(api_key="test")
    with pytest.raises(FileNotFoundError):
        await provider.transcribe(nonexistent)
```

**关键点**：
- 每个 HTTP 错误码用 `parametrize` 一次测多个
- 必测：成功、4xx、5xx、超时、文件错误
- response 样本独立成 fixture，便于多个测试共用

### 4.3 集成测试模板

```python
"""端到端跑一遍 pipeline（用 30 秒短音频 + mock 外部 API）。"""
from __future__ import annotations

from pathlib import Path

import pytest

from podlator.graph.builder import build_graph_only
from podlator.graph.state import make_initial_state


@pytest.fixture
def short_audio() -> Path:
    return Path(__file__).parent.parent / "fixtures" / "audio" / "sample_30s.mp3"


async def test_pipeline_completes_for_short_audio(
    short_audio: Path,
    mock_all_external_apis,   # 来自 conftest.py，mock 所有外部依赖
    tmp_path: Path,
):
    graph = build_graph_only().compile()

    initial = make_initial_state(
        task_id="integration-test-001",
        source_url=f"file://{short_audio}",
        source_type="manual",
    )

    final_state = await graph.ainvoke(initial)

    assert final_state["status"] == "completed"
    assert final_state["output_md_path"] is not None
    assert final_state["output_md_path"].exists()
    assert "errors" not in final_state or len(final_state["errors"]) == 0
```

### 4.4 全局 conftest.py 模板

```python
# tests/conftest.py
"""全局 fixture 和测试配置。"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

# 自动加载测试环境变量
@pytest.fixture(autouse=True)
def _setup_test_env(monkeypatch, tmp_path: Path):
    """每个测试自动隔离环境变量和数据目录。"""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("CLAUDE_API_KEY", "test-key")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


# Smoke 测试 marker
def pytest_collection_modifyitems(config, items):
    """自动跳过 smoke 测试，除非显式开启。"""
    if not os.getenv("PODLATOR_RUN_SMOKE"):
        skip_smoke = pytest.mark.skip(reason="需要 PODLATOR_RUN_SMOKE=1")
        for item in items:
            if "smoke" in item.keywords or "tests/smoke" in str(item.fspath):
                item.add_marker(skip_smoke)
```

---

## 5. 学习路径建议

### 5.1 第 1 周：基础

- [ ] 写 5-10 个最简单的同步测试（断言加减乘除）
- [ ] 熟悉 `pytest -v`、`-k`、`-x`、`--lf` 命令
- [ ] 写 3 个用 `tmp_path` 处理文件的测试
- [ ] 写 3 个用 `monkeypatch.setenv` 的测试
- [ ] 写一个用 `parametrize` 的测试

### 5.2 第 2 周：异步和 Mock

- [ ] 写 5 个 async 测试
- [ ] 用 `pytest-httpx` mock 3 个不同 API 响应
- [ ] 写一个 fixture 并在多个测试中复用
- [ ] 学会看 pytest 失败输出（特别是 `--tb=short` vs `--tb=long`）

### 5.3 第 3 周：设计

- [ ] 在新写一个节点时，**先写测试再写实现**（真正的 TDD）
- [ ] 复盘自己的测试，看是否符合 AAA 模式
- [ ] 检查覆盖率：`uv run pytest --cov --cov-report=html`，打开 `htmlcov/index.html` 看哪些行没覆盖
- [ ] 写一个集成测试

### 5.4 进阶（按需）

- 性能测试：`pytest-benchmark`
- 属性测试：`hypothesis`（自动生成测试输入，发现你想不到的边界）
- 快照测试：`syrupy`（适合测 LLM 输出的稳定性）
- 突变测试：`mutmut`（验证你的测试质量）

---

## 6. 常见问题排查

**Q: `pytest` 找不到模块？**

A: 检查 `pyproject.toml` 的 `[tool.pytest.ini_options]` 是否有 `testpaths = ["tests"]`，以及包是否正确安装（`uv sync` 后会自动 `pip install -e .`）。

**Q: 异步测试报 "no event loop"？**

A: 确认 `asyncio_mode = "auto"` 在 `pyproject.toml` 里。

**Q: Mock 没生效？**

A: 90% 的情况是 mock 错了路径。规则：**mock 使用处而不是定义处**。如果 `nodes/transcribe.py` 里 `from xxx import yyy`，要 mock `nodes.transcribe.yyy`，不是 `xxx.yyy`。

**Q: 测试在本地跑过但 CI 挂？**

A: 通常是隐式依赖（环境变量、时间、文件路径）。用 `pytest-randomly` 本地跑几遍，看是否稳定。

**Q: 一个测试改了文件影响后续测试？**

A: 用 `tmp_path` fixture，别用项目里的真实路径。

**Q: 覆盖率工具显示某行没覆盖但其实测了？**

A: 可能是异步代码或装饰器，加 `--cov-config` 调优；也可能那行真的没被执行，仔细看。

---

## 7. AI IDE 工作时的测试纪律

> 给 AI 看的额外约束（用户也可以参考）

1. **写新功能前**，先列出测试清单贴在回复里给用户看，再开始动手
2. **不要为了让测试过**而修改断言。失败的原因永远先理解后处理
3. **不要 import `unittest.mock` 的 Mock 来 mock 自己的函数**——这是反模式信号
4. **测试名必须能读懂**——读测试名就该知道测什么场景
5. **每次 commit 前**跑一遍 `uv run pytest --cov`，把结果贴在 DoD 自检里
6. **绝不允许 `@pytest.mark.skip` 而不说明原因**——必须写明跳过的理由和恢复条件
7. **flaky 测试立刻修**，不允许"重跑就好了"
