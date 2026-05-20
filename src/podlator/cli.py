"""Podlator CLI 入口。"""

from __future__ import annotations

import typer

app = typer.Typer(help="Podlator — 英文播客/视频 → 中文简报")


@app.command()
def run(
    url: str,
    output_dir: str | None = None,
) -> None:
    """处理单个 URL，产出中文简报。"""
    typer.echo(f"[M0 占位] 将处理: {url}")
    if output_dir:
        typer.echo(f"[M0 占位] 输出目录: {output_dir}")


@app.command()
def status(task_id: str | None = None) -> None:
    """查看任务状态。"""
    if task_id:
        typer.echo(f"[M0 占位] 任务 {task_id} 状态查询")
    else:
        typer.echo("[M0 占位] 最近任务状态查询")


@app.command()
def list(
    status_filter: str | None = typer.Option(None, "--status", help="按状态过滤"),
    limit: int = typer.Option(20, "--limit", help="返回数量"),
) -> None:
    """列出所有任务。"""
    typer.echo(f"[M0 占位] 任务列表 (status={status_filter}, limit={limit})")


@app.command()
def version() -> None:
    """显示版本号。"""
    from podlator import __version__

    typer.echo(f"podlator {__version__}")
