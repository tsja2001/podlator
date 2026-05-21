# M2 — Web UI MVP 开发计划

> **执行前先读 `docs/tasks/EXECUTION-FRAMEWORK.md`。**
> **依赖 M1 完成。** M1 必须已经能通过 CLI 或 API 后台任务跑通 pipeline，并产出 Markdown 简报。
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

---

## 目标

实现 M2 Web UI MVP：用户可以在浏览器提交 URL、查看任务队列、进入任务详情页实时看结构化日志和节点进度，并在任务完成后阅读、复制、下载 Markdown 简报。

## 架构

M2 分两条线推进：后端先补齐“任务执行 + WebSocket 日志广播 + 简报读取”能力，前端再用 TanStack Query + WebSocket hook 消费这些接口。日志广播不能污染现有 structlog 文件/控制台输出，推荐通过一个独立的内存 `LogHub` 接收符合 task_id 的事件，再由 WebSocket 连接按任务订阅。

## 技术栈

- 后端：FastAPI、BackgroundTasks、WebSocket、structlog、SQLite TaskStore、pytest
- 前端：Vite、React、React Router、TanStack Query、shadcn/ui 风格组件、lucide-react、react-markdown、vitest、Testing Library
- 验证：`uv run pytest`、`ruff`、`mypy`、`cd web && pnpm build && pnpm test`

---

## 前置条件

- [ ] M1.1 Provider 实现已完成，Provider 单元测试通过
- [ ] M1.2 节点和 Prompt 实现已完成，节点单元测试通过
- [ ] M1.3 CLI/API pipeline 集成已完成，mock pipeline 集成测试通过
- [ ] `.env` 中已配置 M1 所需 API key；M2 单测不得调用真实 API
- [ ] 至少存在一个已完成任务或可用 fixture，用于验证 BriefViewer

## 预检命令

```bash
uv sync
uv run pytest -x -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
cd web && pnpm install && pnpm build
git status --short
```

预期：除 `git status --short` 可显示本任务文档或后续开发改动外，其余命令必须通过。预检失败时停止，不要进入实现。

---

## 文件结构与职责

### 后端新增/修改

| 文件 | 操作 | 职责 |
|---|---|---|
| `src/podlator/api/pipeline.py` | 新增 | 后台执行 graph，统一更新 TaskStore 状态，供 create/retry 复用 |
| `src/podlator/api/log_hub.py` | 新增 | 按 `task_id` 管理 WebSocket 订阅队列，广播日志事件 |
| `src/podlator/api/ws.py` | 修改 | 从占位连接改为真实订阅日志流 |
| `src/podlator/api/routes.py` | 修改 | `POST /tasks` 触发后台 pipeline；实现 retry 和 brief |
| `src/podlator/api/schemas.py` | 修改 | 补充 Brief、Retry、错误响应所需模型或字段 |
| `src/podlator/api/main.py` | 修改 | lifespan 初始化 `LogHub`，供 routes/ws 使用 |
| `src/podlator/logging.py` | 修改 | 增加可选 WebSocket processor/hook，把 structlog 事件推给 LogHub |
| `tests/unit/api/test_routes.py` | 修改 | 覆盖 create/retry/brief 行为 |
| `tests/unit/api/test_ws.py` | 新增 | 覆盖 WebSocket 订阅、过滤、断开 |
| `tests/unit/api/test_log_hub.py` | 新增 | 覆盖 LogHub 广播和队列清理 |
| `tests/integration/test_websocket_logs.py` | 新增 | mock pipeline 日志推送到 WS 的集成路径 |

### 前端新增/修改

| 文件 | 操作 | 职责 |
|---|---|---|
| `web/package.json` | 修改 | 增加 UI、markdown、测试依赖和 `test` 脚本 |
| `web/src/main.tsx` | 修改 | 注入 `QueryClientProvider` |
| `web/src/lib/api.ts` | 修改 | typed REST client |
| `web/src/lib/task-types.ts` | 新增 | Task、LogEvent、Brief 类型 |
| `web/src/lib/useTaskLogs.ts` | 新增 | WebSocket 日志 hook，负责连接、重连、事件列表 |
| `web/src/components/TaskCard.tsx` | 新增 | 队列任务卡片 |
| `web/src/components/LogViewer.tsx` | 新增 | 实时日志列表、级别/节点过滤、自动滚动 |
| `web/src/components/NodeProgressBar.tsx` | 新增 | 8 个节点状态可视化 |
| `web/src/components/BriefRenderer.tsx` | 新增 | Markdown 渲染、复制、下载 |
| `web/src/pages/SubmitPage.tsx` | 修改 | URL 表单、提交反馈、成功后跳转详情 |
| `web/src/pages/QueuePage.tsx` | 修改 | 任务列表、状态筛选、自动刷新 |
| `web/src/pages/TaskDetailPage.tsx` | 修改 | 任务信息、节点进度、实时日志、简报入口 |
| `web/src/pages/BriefViewerPage.tsx` | 修改 | 拉取并渲染 Markdown 简报 |
| `web/src/App.tsx` | 修改 | 导航和页面布局 |
| `web/src/index.css` | 修改 | 全局样式和 shadcn 风格 token |
| `web/src/**/*.test.tsx` | 新增 | 组件和 hook 测试 |

---

## M2.1 后端：任务执行与 WebSocket 日志

### Phase 1: 后台 pipeline 执行抽离

#### 1.1 新增 `src/podlator/api/pipeline.py`

- [ ] 创建 `run_pipeline_background(task_id, url, store)`，作为 API 后台任务唯一入口。
- [ ] 任务开始时写 `status="running"`，失败时写 `status="failed"` 和 `error_message`，成功时写 `status="completed"`、`title`、`brief_path`、`cost_usd`、`duration_seconds`。
- [ ] 使用 `get_logger(__name__)`，失败必须 `exc_info=True`。

建议实现形状：

```python
"""后台 pipeline 执行入口。"""
from __future__ import annotations

from typing import Any

from podlator.graph.builder import build_graph
from podlator.logging import get_logger
from podlator.storage.db import TaskStore

logger = get_logger(__name__)


async def run_pipeline_background(
    task_id: str,
    source_url: str,
    store: TaskStore,
) -> None:
    """执行单个任务并把最终状态写回数据库。"""
    await store.update(task_id, status="running", current_node="fetch_metadata")
    logger.info("task_started", task_id=task_id, source_url=source_url)

    initial_state: dict[str, Any] = {
        "task_id": task_id,
        "source_url": source_url,
        "status": "running",
        "current_node": "",
        "node_durations_ms": {},
        "total_cost_usd": 0.0,
    }

    try:
        graph = build_graph()
        final_state = await graph.ainvoke(initial_state)
        await store.update(
            task_id,
            status="completed",
            current_node=final_state.get("current_node"),
            title=final_state.get("title"),
            brief_path=final_state.get("output_path"),
            audio_path=final_state.get("audio_path"),
            cost_usd=final_state.get("total_cost_usd", 0.0),
            duration_seconds=final_state.get("duration_seconds"),
            error_message=None,
        )
        logger.info(
            "task_completed",
            task_id=task_id,
            output_path=final_state.get("output_path"),
            cost_usd=final_state.get("total_cost_usd", 0.0),
        )
    except Exception as exc:
        logger.error(
            "task_failed",
            task_id=task_id,
            error_type=type(exc).__name__,
            error_msg=str(exc),
            exc_info=True,
        )
        await store.update(task_id, status="failed", error_message=str(exc))
```

#### 1.2 更新 `src/podlator/api/routes.py`

- [ ] `POST /api/tasks` 增加 `BackgroundTasks` 参数，创建任务后立即 `background_tasks.add_task(run_pipeline_background, task_id, str(body.url), store)`。
- [ ] 返回仍使用 `TaskResponse`，状态初始为 `pending`。
- [ ] `POST /api/tasks/{task_id}/retry` 只允许 `failed` 任务重试；不存在返回 404，非 failed 返回 409。
- [ ] retry 先清空 `error_message`、重置 `brief_path` 可不做，至少重置 `status="pending"`，再添加后台任务。

#### 1.3 后端测试

- [ ] 在 `tests/unit/api/test_routes.py` 增加：
  - `test_create_task_schedules_background_pipeline`
  - `test_retry_failed_task_schedules_pipeline`
  - `test_retry_non_failed_task_returns_409`
  - `test_retry_missing_task_returns_404`
- [ ] 通过 monkeypatch 替换 `podlator.api.routes.run_pipeline_background` 为 no-op spy，避免测试跑真实 graph。

Phase 1 验证：

```bash
uv run pytest tests/unit/api/test_routes.py -v --tb=short
uv run ruff check src/podlator/api tests/unit/api
uv run mypy src/
```

---

### Phase 2: LogHub 与 structlog 广播

#### 2.1 新增 `src/podlator/api/log_hub.py`

- [ ] 实现 `LogHub.subscribe(task_id)`，返回 async context manager 或 async generator。
- [ ] 实现 `LogHub.publish(event)`，只在 event 有 `task_id` 时广播给对应订阅者。
- [ ] 每个订阅者使用 `asyncio.Queue[dict[str, Any]]`，队列上限建议 500；满了丢最旧事件并追加一条 `log_dropped` warning 事件。
- [ ] 断开连接时必须从 subscribers 中移除 queue，避免内存泄漏。

建议接口：

```python
"""任务日志广播中心。"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator


class LogHub:
    """按 task_id 把结构化日志广播给 WebSocket 订阅者。"""

    def __init__(self, max_queue_size: int = 500) -> None:
        self.max_queue_size = max_queue_size
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)

    @asynccontextmanager
    async def subscribe(self, task_id: str) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self.max_queue_size)
        self._subscribers[task_id].add(queue)
        try:
            yield queue
        finally:
            self._subscribers[task_id].discard(queue)
            if not self._subscribers[task_id]:
                del self._subscribers[task_id]

    async def publish(self, event: dict[str, Any]) -> None:
        task_id = event.get("task_id")
        if not isinstance(task_id, str):
            return
        for queue in list(self._subscribers.get(task_id, ())):
            if queue.full():
                _ = queue.get_nowait()
            queue.put_nowait(event)
```

#### 2.2 修改 `src/podlator/logging.py`

- [ ] 增加模块级 `set_log_hub(hub)` 或 `configure_log_broadcast(hub)`。
- [ ] 增加 structlog processor：复制 event_dict，调用 `hub.publish()`。
- [ ] 因 structlog processor 是同步函数，不能直接 `await`；用 `asyncio.get_running_loop().create_task(hub.publish(dict(event_dict)))`。若没有运行中的 event loop，则静默跳过广播，但不得影响文件/控制台日志。
- [ ] processor 必须返回原 `event_dict`，不能改变现有日志输出。

关键要求：

```python
def _broadcast_to_log_hub(
    _logger: WrappedLogger,
    _method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """把带 task_id 的日志事件异步发送到 WebSocket LogHub。"""
    if _log_hub is None or not isinstance(event_dict.get("task_id"), str):
        return event_dict
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return event_dict
    loop.create_task(_log_hub.publish(dict(event_dict)))
    return event_dict
```

#### 2.3 修改 `src/podlator/api/main.py`

- [ ] 在 lifespan 中创建 `LogHub()`，赋值 `app.state.log_hub`。
- [ ] 调用 `set_log_hub(log_hub)`，让 structlog 能广播到 hub。
- [ ] 退出 lifespan 时调用 `set_log_hub(None)`，避免测试之间共享状态。

#### 2.4 单元测试

- [ ] 新增 `tests/unit/api/test_log_hub.py`：
  - `test_publish_delivers_event_to_matching_task`
  - `test_publish_ignores_event_without_task_id`
  - `test_subscribe_removes_queue_after_context_exit`
  - `test_publish_does_not_deliver_to_other_task`
- [ ] 新增或更新日志测试，确认 processor 不改变原 event dict。

Phase 2 验证：

```bash
uv run pytest tests/unit/api/test_log_hub.py tests/unit/test_logging.py -v --tb=short
uv run ruff check src/podlator/logging.py src/podlator/api/log_hub.py
uv run mypy src/
```

---

### Phase 3: WebSocket 日志订阅

#### 3.1 修改 `src/podlator/api/ws.py`

- [ ] 接受连接后从 `websocket.app.state.log_hub` 获取 hub。
- [ ] 立即发送 `{"event": "connected", "task_id": task_id}`，但不关闭连接。
- [ ] 在 `async with hub.subscribe(task_id) as queue:` 中循环 `event = await queue.get()`，然后 `await websocket.send_json(event)`。
- [ ] 捕获 `WebSocketDisconnect`，记录 `log.info("websocket_disconnected", task_id=task_id)`。

#### 3.2 WebSocket 测试

- [ ] 新增 `tests/unit/api/test_ws.py`，用 FastAPI TestClient 或 httpx/ASGI 工具连接 `/ws/tasks/{task_id}/logs`。
- [ ] 测试连接后收到 `connected`。
- [ ] 测试向 `app.state.log_hub.publish({"task_id": task_id, "event": "node_started"})` 后客户端收到该事件。
- [ ] 测试另一个 task_id 的事件不会串流。

#### 3.3 集成测试

- [ ] 新增 `tests/integration/test_websocket_logs.py`：
  - 启动 app test client
  - 连接 task logs WebSocket
  - 通过 logger 写一条带 task_id 的日志
  - 断言 WebSocket 收到相同 event

Phase 3 验证：

```bash
uv run pytest tests/unit/api/test_ws.py tests/integration/test_websocket_logs.py -v --tb=short
uv run pytest tests/unit/api/ tests/integration/ -v --tb=short
```

---

### Phase 4: Brief API 完成

#### 4.1 修改 `src/podlator/api/routes.py`

- [ ] 实现 `GET /api/tasks/{task_id}/brief`。
- [ ] 不存在返回 404。
- [ ] 任务未 completed 返回 400，错误信息说明“任务尚未完成，不能读取简报”。
- [ ] `brief_path` 为空或文件不存在返回 404，错误信息说明“简报文件不存在或已被删除”。
- [ ] 正常读取 Markdown，返回 `TaskBriefResponse(task_id, title, markdown)`。

#### 4.2 测试

- [ ] 增加：
  - `test_get_brief_success`
  - `test_get_brief_task_not_found`
  - `test_get_brief_not_completed_returns_400`
  - `test_get_brief_missing_file_returns_404`

Phase 4 验证：

```bash
uv run pytest tests/unit/api/test_routes.py -v --tb=short
uv run pytest -x -q
```

---

## M2.2 前端：Web UI MVP

### Phase 5: 前端依赖、测试框架与 QueryProvider

#### 5.1 安装依赖

- [ ] 增加运行时依赖：

```bash
cd web && pnpm add @tanstack/react-query lucide-react react-markdown remark-gfm
```

- [ ] 增加测试依赖：

```bash
cd web && pnpm add -D vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

#### 5.2 修改 `web/package.json`

- [ ] 增加：

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

#### 5.3 修改 `web/vite.config.ts`

- [ ] 配置 vitest：

```ts
/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
```

#### 5.4 新增 `web/src/test/setup.ts`

```ts
import "@testing-library/jest-dom/vitest";
```

#### 5.5 修改 `web/src/main.tsx`

- [ ] 创建 `QueryClient` 并包裹 App。
- [ ] 默认 query staleTime 设为 5 秒，减少重复请求。

Phase 5 验证：

```bash
cd web && pnpm test
cd web && pnpm build
```

---

### Phase 6: Typed API Client

#### 6.1 新增 `web/src/lib/task-types.ts`

```ts
export type TaskStatus = "pending" | "running" | "completed" | "failed";

export interface Task {
  task_id: string;
  source_url: string;
  title: string | null;
  status: TaskStatus;
  current_node: string | null;
  error_message: string | null;
  cost_usd: number;
  created_at: string;
  updated_at: string;
}

export interface TaskBrief {
  task_id: string;
  title: string | null;
  markdown: string;
}

export interface LogEvent {
  timestamp?: string;
  level?: "debug" | "info" | "warning" | "error" | "critical";
  logger?: string;
  event: string;
  task_id: string;
  node?: string;
  message?: string;
  duration_ms?: number;
  cost_usd?: number;
  error_msg?: string;
  [key: string]: unknown;
}
```

#### 6.2 修改 `web/src/lib/api.ts`

- [ ] 实现 `fetchTasks(status?)`、`fetchTask(taskId)`、`createTask(url)`、`retryTask(taskId)`、`fetchBrief(taskId)`。
- [ ] 统一处理非 2xx：读取 `detail` 并抛 `Error`，给页面 toast/错误区展示。
- [ ] API base 使用 `import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api"`。

建议函数签名：

```ts
import type { Task, TaskBrief, TaskStatus } from "./task-types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
```

#### 6.3 API Client 测试

- [ ] 新增 `web/src/lib/api.test.ts`，mock `global.fetch`。
- [ ] 覆盖成功和错误响应。

Phase 6 验证：

```bash
cd web && pnpm test -- src/lib/api.test.ts
cd web && pnpm build
```

---

### Phase 7: WebSocket hook

#### 7.1 新增 `web/src/lib/useTaskLogs.ts`

- [ ] 输入 `taskId: string | undefined`。
- [ ] 输出 `{ logs, connectionStatus, clearLogs }`。
- [ ] WS URL 使用 `VITE_WS_BASE_URL ?? "ws://localhost:8000"`，路径为 `/ws/tasks/${taskId}/logs`。
- [ ] 收到 JSON 后 append 到 logs；最多保留最近 1000 条。
- [ ] 连接断开时若任务仍存在，2 秒后重连；组件卸载时关闭连接。

#### 7.2 Hook 测试

- [ ] 新增 `web/src/lib/useTaskLogs.test.tsx`。
- [ ] 使用 fake WebSocket class 测试：
  - 连接 URL 正确
  - 收到消息后 logs 增加
  - `clearLogs()` 清空日志
  - unmount 时关闭 WebSocket

Phase 7 验证：

```bash
cd web && pnpm test -- src/lib/useTaskLogs.test.tsx
cd web && pnpm build
```

---

### Phase 8: 基础 UI 组件

#### 8.1 新增 `web/src/components/TaskCard.tsx`

- [ ] 展示 title/source_url、status、current_node、cost_usd、created_at。
- [ ] 状态 badge 使用固定颜色，不要只靠颜色表达状态，文本也要显示。
- [ ] 点击进入 `/tasks/${task.task_id}`。

#### 8.2 新增 `web/src/components/NodeProgressBar.tsx`

- [ ] 固定节点顺序：

```ts
const PIPELINE_NODES = [
  "fetch_metadata",
  "download_audio",
  "transcribe",
  "diarize",
  "chapter_split",
  "summarize_chapters",
  "polish_final",
  "export_markdown",
] as const;
```

- [ ] 根据 `task.status` 和 `task.current_node` 推断每个节点为 `done | running | pending | failed`。
- [ ] `diarize` 可能被跳过，M2 先显示为 pending 或 skipped 均可，但文案要稳定。

#### 8.3 新增 `web/src/components/LogViewer.tsx`

- [ ] 支持按 level、node 过滤。
- [ ] 支持搜索 event/message/error_msg。
- [ ] 默认自动滚动到底部，用户切换“暂停滚动”后停止。
- [ ] 每条日志显示时间、级别、节点、event、关键字段。

#### 8.4 新增 `web/src/components/BriefRenderer.tsx`

- [ ] 使用 `react-markdown` + `remark-gfm` 渲染 Markdown。
- [ ] 提供复制按钮：`navigator.clipboard.writeText(markdown)`。
- [ ] 提供下载按钮：创建 Blob + `<a download>`。
- [ ] 复制失败时显示页面内错误提示。

#### 8.5 组件测试

- [ ] 为每个组件写至少 1 个正常渲染测试。
- [ ] `LogViewer` 额外测 level 过滤。
- [ ] `BriefRenderer` 额外测 markdown 标题渲染和复制按钮调用 clipboard。

Phase 8 验证：

```bash
cd web && pnpm test -- src/components
cd web && pnpm build
```

---

### Phase 9: 页面实现

#### 9.1 `SubmitPage`

- [ ] 表单包含 URL 输入框和提交按钮。
- [ ] 使用 `useMutation({ mutationFn: createTask })`。
- [ ] 提交成功后 invalidate tasks query，并跳转 `/tasks/${task_id}`。
- [ ] 输入为空或不是 URL 时在页面内显示错误；后端错误也显示，不白屏。

#### 9.2 `QueuePage`

- [ ] 使用 `useQuery` 拉取任务列表。
- [ ] 状态筛选：`all | pending | running | completed | failed`。
- [ ] `refetchInterval: 3000`，保证队列自动刷新。
- [ ] 空状态显示“暂无任务”，失败状态显示错误和重试按钮。

#### 9.3 `TaskDetailPage`

- [ ] 从 URL params 获取 `taskId`。
- [ ] `useQuery(fetchTask)` 每 2 秒刷新任务详情。
- [ ] `useTaskLogs(taskId)` 订阅实时日志。
- [ ] 展示基本信息、`NodeProgressBar`、`LogViewer`。
- [ ] completed 时显示“查看简报”按钮，跳转 `/tasks/${taskId}/brief`。
- [ ] failed 时显示错误和 retry 按钮。

#### 9.4 `BriefViewerPage`

- [ ] `useQuery(fetchBrief)` 拉取 Markdown。
- [ ] loading/error/empty 状态完整。
- [ ] 使用 `BriefRenderer` 渲染。
- [ ] 提供返回任务详情和返回队列入口。

#### 9.5 `App.tsx` 与样式

- [ ] 导航使用稳定布局，页面宽度约束在 `max-width: 1120px`。
- [ ] 风格保持工具型、信息密度适中，不做营销 hero。
- [ ] 不新增无关插画或装饰性背景。
- [ ] 所有按钮/输入在 375px 移动宽度下不溢出。

Phase 9 验证：

```bash
cd web && pnpm test
cd web && pnpm build
```

---

## 最终验证

### 后端

```bash
uv run pytest -v --tb=short
uv run pytest --cov --cov-report=term-missing --cov-fail-under=70
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
```

### 前端

```bash
cd web && pnpm test
cd web && pnpm lint
cd web && pnpm build
```

### 手动联调

```bash
uv run uvicorn podlator.api.main:app --reload --port 8000
cd web && pnpm dev
```

浏览器访问 `http://localhost:5173`，按顺序验证：

- [ ] `/` 提交 URL 后跳转任务详情页
- [ ] `/queue` 出现新任务，状态自动刷新
- [ ] `/tasks/:id` WebSocket 显示 `connected` 和后续 structlog 事件
- [ ] 任务完成后出现“查看简报”
- [ ] `/tasks/:id/brief` 正常渲染 Markdown
- [ ] API 错误显示在页面内，不出现白屏

---

## 完成报告模板

执行者完成 M2 后必须输出：

```markdown
# M2 完成报告

## 执行摘要
- **任务**: Web UI MVP（任务提交、队列、实时日志、简报浏览）
- **状态**: ✅ 完成 / ⚠️ 部分完成 / ❌ 失败
- **后端新增/修改文件**: N 个
- **前端新增/修改文件**: N 个
- **新增测试数**: N 个

## 文件变更清单

| 文件 | 操作 | 说明 |
|---|---|---|
| `src/podlator/api/log_hub.py` | 新增 | WebSocket 日志广播中心 |
| `web/src/components/LogViewer.tsx` | 新增 | 实时日志面板 |

## 测试结果

```text
粘贴后端 pytest 和前端 pnpm test 的关键输出
```

## 代码质量

```text
粘贴 ruff、mypy、pnpm lint、pnpm build 的关键输出
```

## 手动联调

- [x] 提交 URL 成功
- [x] 队列自动刷新
- [x] WebSocket 实时日志可见
- [x] Markdown 简报可阅读、复制、下载

## 已知问题

无 / 列出问题、影响、后续建议。

## DoD 自检

### 代码质量
- [x] 类型注解齐全
- [x] ruff check 通过
- [x] ruff format 通过
- [x] mypy 通过
- [x] pnpm lint 通过
- [x] pnpm build 通过

### 测试
- [x] 后端 unit/integration 测试通过
- [x] 前端组件/hook/API 测试通过
- [x] WebSocket 连接和日志过滤已覆盖
- [x] 错误场景已覆盖
- [x] 覆盖率 >= 70%

### 日志
- [x] task_started/task_completed/task_failed 日志齐全
- [x] WebSocket 断开有日志
- [x] 无 print()

### 文档
- [x] CHANGELOG.md 已更新
- [x] README.md 已更新（如新增前端运行/测试命令）
- [x] docs/ARCHITECTURE.md 已更新（如 API 或前端路由变更）

### 验证
- [x] uvicorn 能启动
- [x] Web UI 能访问
- [x] 手动联调通过

✅ M2 满足 DoD，可以提交。
```

---

## 风险与边界

- M2 不做 RSS、成本统计页、Prompt 质量评估、本地 STT、TTS。
- M2 不引入复杂队列系统；FastAPI `BackgroundTasks` 足够支撑自用 MVP。
- WebSocket 只承载实时日志，不负责补历史日志。若用户刷新页面，历史日志可在 M3/M5 通过读取 `data/logs/podlator.log` 再补。
- 如果 M1 的 API 后台执行尚未完成，先补齐 M1.3 的 API pipeline 部分，再进入本计划。
- 如果要引入 shadcn CLI 自动生成组件，执行者可以使用；但不得为了 UI 组件重构整个前端目录。
