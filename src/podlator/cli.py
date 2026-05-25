"""Podlator CLI 入口。"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import typer

app = typer.Typer(help="Podlator — 英文播客/视频 → 中文简报")


@app.command()
def run(
    url: str = typer.Argument(..., help="YouTube 或播客 URL"),
    output_dir: str | None = typer.Option(None, help="输出目录"),
) -> None:
    """处理单个 URL，产出中文简报。"""
    asyncio.run(_run_pipeline(url, output_dir))


async def _run_pipeline(url: str, output_dir: str | None) -> None:
    """异步执行 pipeline。"""
    from podlator.config import Settings
    from podlator.graph.builder import build_graph
    from podlator.logging import setup_logging
    from podlator.storage.db import TaskStore

    settings = Settings()
    log_dir = settings.log_dir if output_dir is None else None
    setup_logging(settings.log_level, settings.log_json_enabled, log_dir=log_dir)

    # 1. 创建任务记录
    store = TaskStore(settings.database_path)
    await store.initialize()

    try:
        task_id = str(uuid.uuid4())
        await store.create(task_id, url)

        typer.echo(f"任务创建: {task_id}")
        typer.echo(f"处理 URL: {url}")

        # 2. 构建并执行 Graph
        graph = build_graph()

        initial_state: dict[str, Any] = {
            "task_id": task_id,
            "source_url": url,
            "status": "running",
            "current_node": "",
            "node_durations_ms": {},
            "total_cost_usd": 0.0,
        }

        try:
            final_state = await graph.ainvoke(initial_state)  # type: ignore[call-overload]

            await store.update(
                task_id,
                status="completed",
                title=final_state.get("title"),
                brief_path=final_state.get("output_path"),
                cost_usd=final_state.get("total_cost_usd", 0.0),
                duration_seconds=final_state.get("duration_seconds"),
            )

            output_path = final_state.get("output_path", "unknown")
            cost = final_state.get("total_cost_usd", 0.0)

            typer.echo("\n✅ 处理完成!")
            typer.echo(f"   简报: {output_path}")
            typer.echo(f"   费用: ${cost:.4f}")

        except Exception as e:
            await store.update(task_id, status="failed", error_message=str(e))
            typer.echo(f"\n❌ 处理失败: {e}", err=True)
            raise typer.Exit(code=1) from e
    finally:
        await store.close()


@app.command()
def status(
    task_id: str | None = typer.Argument(None, help="任务 ID（不指定则显示最近任务）"),
) -> None:
    """查看任务状态。"""
    asyncio.run(_show_status(task_id))


async def _show_status(task_id: str | None) -> None:
    """查询任务状态。"""
    from podlator.config import Settings
    from podlator.storage.db import TaskStore

    settings = Settings()
    store = TaskStore(settings.database_path)
    await store.initialize()

    try:
        if task_id:
            task = await store.get(task_id)
            if not task:
                typer.echo(f"任务不存在: {task_id}", err=True)
                raise typer.Exit(code=1)
            _print_task(task)
        else:
            tasks = await store.list_tasks(limit=1)
            if not tasks:
                typer.echo("暂无任务")
            else:
                _print_task(tasks[0])
    finally:
        await store.close()


def _print_task(task: dict[str, Any]) -> None:
    """格式化输出任务信息。"""
    typer.echo(f"ID:     {task['id']}")
    typer.echo(f"标题:   {task.get('title', '(未知)')}")
    typer.echo(f"状态:   {task['status']}")
    typer.echo(f"节点:   {task.get('current_node', '-')}")
    typer.echo(f"费用:   ${task.get('cost_usd', 0):.4f}")
    typer.echo(f"创建:   {task['created_at']}")
    if task.get("error_message"):
        typer.echo(f"错误:   {task['error_message']}")
    if task.get("brief_path"):
        typer.echo(f"简报:   {task['brief_path']}")


@app.command()
def list(
    status_filter: str | None = typer.Option(None, "--status", help="按状态过滤"),
    limit: int = typer.Option(20, "--limit", help="返回数量"),
) -> None:
    """列出所有任务。"""
    asyncio.run(_list_tasks(status_filter, limit))


async def _list_tasks(status_filter: str | None, limit: int) -> None:
    """查询任务列表。"""
    from podlator.config import Settings
    from podlator.storage.db import TaskStore

    settings = Settings()
    store = TaskStore(settings.database_path)
    await store.initialize()

    try:
        tasks = await store.list_tasks(status=status_filter, limit=limit)
        if not tasks:
            typer.echo("暂无任务")
            return

        for task in tasks:
            _print_task(task)
            typer.echo("---")
    finally:
        await store.close()


@app.command()
def version() -> None:
    """显示版本号。"""
    from podlator import __version__

    typer.echo(f"podlator {__version__}")
