"""Podlator CLI 入口。"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Annotated, Any

import typer

app = typer.Typer(help="Podlator — 英文播客/视频 → 中文简报")

# ── 全局共享选项 ──


def _resolve_output(input_path: Path, output: Path | None, suffix: str) -> Path:
    """如果 -o 是目录则自动生成文件名，否则用 -o 值。"""
    if output is None:
        raise typer.BadParameter("必须指定 -o/--output 输出路径")
    if output.is_dir() or (output.suffix == "" and not output.exists()):
        # 目录或看起来像目录的路径
        output.mkdir(parents=True, exist_ok=True)
        return output / f"{input_path.stem}{suffix}"
    output.parent.mkdir(parents=True, exist_ok=True)
    return output


# ── run（保留原有完整 pipeline）──


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

    store = TaskStore(settings.database_path)
    await store.initialize()

    try:
        task_id = str(uuid.uuid4())
        await store.create(task_id, url)

        typer.echo(f"任务创建: {task_id}")
        typer.echo(f"处理 URL: {url}")

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


# ── status / list / version（保留）──


@app.command()
def status(
    task_id: str | None = typer.Argument(None, help="任务 ID（不指定则显示最近任务）"),
) -> None:
    """查看任务状态。"""
    asyncio.run(_show_status(task_id))


async def _show_status(task_id: str | None) -> None:
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


# ── 文件转换型 Step CLI ──


@app.command()
def download(
    url: str = typer.Argument(..., help="YouTube 或播客 URL"),
    output: Annotated[
        Path | None,
        typer.Option("-o", "--output", help="输出音频文件路径"),
    ] = None,
    metadata: Annotated[
        Path | None,
        typer.Option("--metadata", help="输出 metadata JSON 路径（可选）"),
    ] = None,
) -> None:
    """下载音频：URL → 音频文件 + 可选 metadata JSON。"""
    asyncio.run(_download_cmd(url, output, metadata))


async def _download_cmd(url: str, output: Path | None, metadata: Path | None) -> None:
    from podlator.steps.download import download_audio

    typer.echo(f"下载: {url}")

    result, meta = await download_audio(url)

    if output:
        out = _resolve_output(Path("audio"), output, ".mp3")
        import shutil

        shutil.copy2(Path(result.file_path), out)
        typer.echo(f"音频: {out}")
    else:
        typer.echo(f"音频: {Path(result.file_path)}")

    if metadata:
        import json

        meta_dict = {
            "title": meta.title,
            "description": meta.description,
            "duration_seconds": meta.duration_seconds,
            "published_at": meta.published_at,
            "source_type": meta.source_type,
            "thumbnail_url": meta.thumbnail_url,
        }
        metadata.parent.mkdir(parents=True, exist_ok=True)
        metadata.write_text(
            json.dumps(meta_dict, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        typer.echo(f"元数据: {metadata}")


@app.command()
def transcribe(
    audio: Annotated[Path, typer.Argument(help="音频文件路径 (.mp3/.m4a/.wav)")],
    output: Annotated[
        Path | None,
        typer.Option("-o", "--output", help="输出 Transcript JSON 路径"),
    ] = None,
    provider: Annotated[
        str | None,
        typer.Option("--provider", help="Provider 名称（默认从配置读取）"),
    ] = None,
    speech_transcriber_dir: Annotated[
        str | None,
        typer.Option(
            "--speech-transcriber-dir",
            help="speech-transcriber 项目目录路径",
        ),
    ] = None,
) -> None:
    """语音转文字：音频文件 → Transcript JSON。

    通过外部 speech-transcriber CLI 完成转写。
    """
    asyncio.run(_transcribe_cmd(audio, output, provider, speech_transcriber_dir))


async def _transcribe_cmd(
    audio: Path,
    output: Path | None,
    provider: str | None,
    speech_transcriber_dir: str | None,
) -> None:
    from podlator.config import Settings
    from podlator.steps.transcribe import transcribe_to_file

    if not audio.exists():
        typer.echo(f"音频文件不存在: {audio}", err=True)
        raise typer.Exit(code=1)

    settings = Settings()
    provider_name = provider or settings.speech_transcriber_provider
    project_dir = speech_transcriber_dir or settings.speech_transcriber_project_dir

    if output is None:
        output = audio.parent / f"{audio.stem}.transcript.json"

    try:
        doc = await transcribe_to_file(
            audio,
            output,
            provider_name=provider_name,
            speech_transcriber_project_dir=project_dir,
        )
        typer.echo(f"转录完成: {output}")
        typer.echo(f"  时长: {doc.source.duration_seconds:.0f}s")
        typer.echo(f"  片段: {len(doc.segments)}")
        typer.echo(f"  字数: {len(doc.text)}")
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        typer.echo(f"转录失败: {e}", err=True)
        raise typer.Exit(code=1) from e


@app.command(name="parse-srt")
def parse_srt(
    srt: Annotated[Path, typer.Argument(help="SRT 字幕文件路径", exists=True)],
    output: Annotated[
        Path,
        typer.Option("-o", "--output", help="输出 Transcript JSON 路径"),
    ] = ...,  # type: ignore[assignment]  # required
    assign_speakers: Annotated[
        bool,
        typer.Option(
            "--assign-speakers",
            help="解析后继续调用 LLM 推断说话人标签",
        ),
    ] = False,
    source_url: Annotated[
        str | None,
        typer.Option("--source-url", help="来源 URL（可选）"),
    ] = None,
    title: Annotated[
        str | None,
        typer.Option("--title", help="节目标题（可选）"),
    ] = None,
    llm_provider: Annotated[
        str | None,
        typer.Option(
            "--llm-provider", help="LLM provider（配合 --assign-speakers 使用）"
        ),
    ] = None,
) -> None:
    """解析字幕：SRT 文件 → Transcript JSON。

    默认不调用 LLM。使用 --assign-speakers 启用说话人推断。
    """
    from podlator.steps.parse_srt import parse_srt_to_file

    try:
        doc = parse_srt_to_file(srt, output, source_url=source_url, title=title)
    except (FileNotFoundError, ValueError) as e:
        typer.echo(f"解析失败: {e}", err=True)
        raise typer.Exit(code=1) from e

    typer.echo(f"字幕解析完成: {output}")
    typer.echo(f"  片段: {len(doc.segments)}")

    if assign_speakers:
        asyncio.run(_assign_speakers_after_parse(output, output, llm_provider))


async def _assign_speakers_after_parse(
    input_path: Path, output_path: Path, provider: str | None
) -> None:
    """parse-srt 后继续做说话人推断。"""
    from podlator.config import Settings
    from podlator.steps.assign_speakers import assign_speakers
    from podlator.steps.io import read_transcript, write_transcript

    settings = Settings()
    provider_name = provider or settings.llm_provider_summarize

    try:
        transcript = read_transcript(input_path)
        result = await assign_speakers(
            transcript, provider_name=provider_name, settings=settings
        )
        write_transcript(output_path, result)
        typer.echo(f"说话人推断完成: {output_path}")
    except Exception as e:
        typer.echo(f"说话人推断失败: {e}", err=True)
        raise typer.Exit(code=1) from e


@app.command(name="assign-speakers")
def assign_speakers_cmd(
    transcript: Annotated[
        Path, typer.Argument(help="Transcript JSON 路径", exists=True)
    ],
    output: Annotated[
        Path,
        typer.Option("-o", "--output", help="输出 Transcript JSON 路径"),
    ] = ...,  # type: ignore[assignment]
    provider: Annotated[
        str | None,
        typer.Option("--provider", help="LLM provider 名称"),
    ] = None,
) -> None:
    """推断说话人：Transcript JSON → 带 speaker 的 Transcript JSON。

    只修改 speaker 字段，不改写正文和时间戳。
    """
    asyncio.run(_assign_speakers_cmd(transcript, output, provider))


async def _assign_speakers_cmd(
    transcript_path: Path, output: Path, provider: str | None
) -> None:
    from podlator.config import Settings
    from podlator.steps.assign_speakers import assign_speakers
    from podlator.steps.io import read_transcript, write_transcript

    settings = Settings()
    provider_name = provider or settings.llm_provider_summarize

    try:
        doc = read_transcript(transcript_path)
    except (FileNotFoundError, ValueError) as e:
        typer.echo(f"读取 Transcript 失败: {e}", err=True)
        raise typer.Exit(code=1) from e

    try:
        result = await assign_speakers(
            doc, provider_name=provider_name, settings=settings
        )
        write_transcript(output, result)
    except Exception as e:
        typer.echo(f"说话人推断失败: {e}", err=True)
        raise typer.Exit(code=1) from e

    changed = sum(
        1 for s, r in zip(doc.segments, result.segments) if s.speaker != r.speaker
    )
    typer.echo(f"说话人推断完成: {output}")
    typer.echo(f"  修改了 {changed}/{len(doc.segments)} 个片段的 speaker 标签")


@app.command()
def split(
    transcript: Annotated[
        Path, typer.Argument(help="Transcript JSON 路径", exists=True)
    ],
    output: Annotated[
        Path,
        typer.Option("-o", "--output", help="输出 Chapters JSON 路径"),
    ] = ...,  # type: ignore[assignment]
    provider: Annotated[
        str | None,
        typer.Option("--provider", help="LLM provider 名称"),
    ] = None,
) -> None:
    """切分章节：Transcript JSON → Chapters JSON。

    只输出章节结构（start/end + title），不翻译、不摘要、不润色正文。
    """
    asyncio.run(_split_cmd(transcript, output, provider))


async def _split_cmd(transcript_path: Path, output: Path, provider: str | None) -> None:
    from podlator.config import Settings
    from podlator.steps.io import read_transcript, write_chapters
    from podlator.steps.split_chapters import split_transcript

    settings = Settings()
    provider_name = provider or settings.llm_provider_summarize

    try:
        doc = read_transcript(transcript_path)
    except (FileNotFoundError, ValueError) as e:
        typer.echo(f"读取 Transcript 失败: {e}", err=True)
        raise typer.Exit(code=1) from e

    try:
        chapters_doc = await split_transcript(
            doc, provider_name=provider_name, settings=settings
        )
        write_chapters(output, chapters_doc)
    except ValueError as e:
        typer.echo(f"章节切分失败: {e}", err=True)
        raise typer.Exit(code=1) from e

    typer.echo(f"章节切分完成: {output}")
    typer.echo(f"  章节数: {len(chapters_doc.chapters)}")
    for ch in chapters_doc.chapters:
        typer.echo(f"  [{ch.start:.0f}s - {ch.end:.0f}s] {ch.title}")


@app.command()
def render(
    transcript: Annotated[
        Path, typer.Argument(help="Transcript JSON 路径", exists=True)
    ],
    chapters: Annotated[
        Path,
        typer.Option("--chapters", help="Chapters JSON 路径", exists=True),
    ] = ...,  # type: ignore[assignment]  # required
    output: Annotated[
        Path,
        typer.Option("-o", "--output", help="输出 Markdown 路径"),
    ] = ...,  # type: ignore[assignment]
    mode: Annotated[
        str,
        typer.Option("--mode", help="输出模式：summary（精简摘要）或 full（全文翻译）"),
    ] = "summary",
    provider: Annotated[
        str | None,
        typer.Option("--provider", help="LLM provider 名称"),
    ] = None,
) -> None:
    """渲染输出：Transcript + Chapters → Markdown。

    支持 summary（精简摘要）和 full（全文翻译）两种模式。
    """
    asyncio.run(_render_cmd(transcript, chapters, output, mode, provider))


async def _render_cmd(
    transcript_path: Path,
    chapters_path: Path,
    output: Path,
    mode: str,
    provider: str | None,
) -> None:
    from podlator.config import Settings
    from podlator.steps.io import read_chapters, read_transcript, write_markdown
    from podlator.steps.render_chinese import render_chinese

    if mode not in ("summary", "full"):
        typer.echo(f"不支持的模式: {mode}（仅支持 summary / full）", err=True)
        raise typer.Exit(code=1)

    settings = Settings()
    provider_name = provider or settings.llm_provider_summarize

    try:
        transcript_doc = read_transcript(transcript_path)
        chapters_doc = read_chapters(chapters_path)
    except (FileNotFoundError, ValueError) as e:
        typer.echo(f"读取文件失败: {e}", err=True)
        raise typer.Exit(code=1) from e

    try:
        md = await render_chinese(
            transcript_doc,
            chapters_doc,
            mode=mode,  # type: ignore[arg-type]
            provider_name=provider_name,
            settings=settings,
        )
        write_markdown(output, md)
    except ValueError as e:
        typer.echo(f"渲染失败: {e}", err=True)
        raise typer.Exit(code=1) from e

    typer.echo(f"渲染完成 ({mode}): {output}")
    typer.echo(f"  字数: {len(md)}")


@app.command()
def polish(
    draft: Annotated[Path, typer.Argument(help="Markdown 草稿路径", exists=True)],
    output: Annotated[
        Path,
        typer.Option("-o", "--output", help="输出 Markdown 路径"),
    ] = ...,  # type: ignore[assignment]
    title: Annotated[
        str | None,
        typer.Option("--title", help="节目标题（可选）"),
    ] = None,
    provider: Annotated[
        str | None,
        typer.Option("--provider", help="LLM provider 名称"),
    ] = None,
) -> None:
    """润色：Markdown 草稿 → 润色后的 Markdown。"""
    asyncio.run(_polish_cmd(draft, output, title, provider))


async def _polish_cmd(
    draft_path: Path, output: Path, title: str | None, provider: str | None
) -> None:
    from podlator.config import Settings
    from podlator.steps.io import read_markdown, write_markdown
    from podlator.steps.polish import polish_markdown

    settings = Settings()
    provider_name = provider or settings.llm_provider_polish

    try:
        md = read_markdown(draft_path)
    except FileNotFoundError as e:
        typer.echo(f"读取草稿失败: {e}", err=True)
        raise typer.Exit(code=1) from e

    try:
        polished = await polish_markdown(
            md, title=title, provider_name=provider_name, settings=settings
        )
        write_markdown(output, polished)
    except Exception as e:
        typer.echo(f"润色失败: {e}", err=True)
        raise typer.Exit(code=1) from e

    typer.echo(f"润色完成: {output}")
    typer.echo(f"  字数: {len(polished)}")


@app.command(name="douyin-script")
def douyin_script(
    transcript: Annotated[
        Path,
        typer.Argument(
            help="Transcript JSON 路径（建议已标注说话人）",
            exists=True,
        ),
    ],
    output: Annotated[
        Path,
        typer.Option("-o", "--output", help="输出 Markdown 路径"),
    ] = ...,  # type: ignore[assignment]  # required
    title: Annotated[
        str | None,
        typer.Option("--title", help="节目标题（默认使用 transcript 中记录的标题）"),
    ] = None,
    provider: Annotated[
        str | None,
        typer.Option("--provider", help="LLM provider 名称（默认 claude，质量更高）"),
    ] = None,
    target_words: Annotated[
        int,
        typer.Option("--target-words", help="目标字数（默认 3000）"),
    ] = 3000,
) -> None:
    """生成抖音解说稿：Transcript JSON → 口语化中文解说稿 Markdown。

    产出风格：钩子开场、解说者视角、按主题重组、术语白话化、
    穿插外部知识、口语化有节奏。

    建议先用 assign-speakers 标注说话人，效果更好。
    """
    asyncio.run(_douyin_script_cmd(transcript, output, title, provider, target_words))


async def _douyin_script_cmd(
    transcript_path: Path,
    output: Path,
    title: str | None,
    provider: str | None,
    target_words: int,
) -> None:
    from podlator.config import Settings
    from podlator.steps.douyin_script import generate_douyin_script
    from podlator.steps.io import read_transcript, write_markdown

    settings = Settings()
    provider_name = provider or settings.llm_provider_polish

    try:
        doc = read_transcript(transcript_path)
    except (FileNotFoundError, ValueError) as e:
        typer.echo(f"读取 Transcript 失败: {e}", err=True)
        raise typer.Exit(code=1) from e

    try:
        script = await generate_douyin_script(
            doc,
            title=title,
            provider_name=provider_name,
            settings=settings,
            target_words=target_words,
        )
        write_markdown(output, script)
    except ValueError as e:
        typer.echo(f"生成失败: {e}", err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.echo(f"生成失败 (LLM 错误): {e}", err=True)
        raise typer.Exit(code=1) from e

    typer.echo(f"解说稿生成完成: {output}")
    typer.echo(f"  字数: {len(script)}")


@app.command(name="pipeline-douyin")
def pipeline_douyin(
    srt: Annotated[
        Path,
        typer.Argument(
            help="SRT 字幕文件路径",
            exists=True,
        ),
    ],
    output: Annotated[
        Path,
        typer.Option("-o", "--output", help="输出 Markdown 路径"),
    ] = ...,  # type: ignore[assignment]  # required
    title: Annotated[
        str | None,
        typer.Option("--title", help="节目标题（默认从文件名推断）"),
    ] = None,
    speaker_provider: Annotated[
        str | None,
        typer.Option(
            "--speaker-provider", help="说话人分离 LLM provider（默认 deepseek）"
        ),
    ] = None,
    script_provider: Annotated[
        str | None,
        typer.Option("--script-provider", help="解说稿 LLM provider（默认 claude）"),
    ] = None,
    target_words: Annotated[
        int,
        typer.Option("--target-words", help="目标字数（默认 3000）"),
    ] = 3000,
    skip_speakers: Annotated[
        bool,
        typer.Option("--skip-speakers", help="跳过说话人分离（SRT 已标注或只有单人）"),
    ] = False,
) -> None:
    """一键流水线：SRT 字幕 → 抖音解说稿 Markdown。

    自动执行：
    1. parse-srt（解析字幕）
    2. assign-speakers（说话人分离，可用 --skip-speakers 跳过）
    3. douyin-script（生成解说稿）
    """
    asyncio.run(
        _pipeline_douyin_cmd(
            srt,
            output,
            title,
            speaker_provider,
            script_provider,
            target_words,
            skip_speakers,
        )
    )


async def _pipeline_douyin_cmd(
    srt_path: Path,
    output: Path,
    title: str | None,
    speaker_provider: str | None,
    script_provider: str | None,
    target_words: int,
    skip_speakers: bool,
) -> None:
    from podlator.config import Settings
    from podlator.steps.assign_speakers import assign_speakers
    from podlator.steps.douyin_script import generate_douyin_script
    from podlator.steps.io import write_markdown
    from podlator.steps.parse_srt import parse_srt_file

    settings = Settings()
    sp_provider = speaker_provider or settings.llm_provider_summarize
    sc_provider = script_provider or settings.llm_provider_polish

    # Step 1: parse-srt
    typer.echo(f"[1/3] 解析字幕: {srt_path}")
    try:
        doc = parse_srt_file(srt_path, title=title)
    except (FileNotFoundError, ValueError) as e:
        typer.echo(f"解析失败: {e}", err=True)
        raise typer.Exit(code=1) from e

    typer.echo(f"  片段数: {len(doc.segments)}")
    duration_m = (doc.source.duration_seconds or 0) / 60
    typer.echo(f"  时长: {duration_m:.0f} 分钟")

    # Step 2: assign-speakers (optional)
    if skip_speakers:
        typer.echo("[2/3] 跳过说话人分离")
    else:
        typer.echo(f"[2/3] 说话人分离 (provider: {sp_provider})")
        try:
            doc = await assign_speakers(
                doc, provider_name=sp_provider, settings=settings
            )
        except Exception as e:
            typer.echo(f"说话人分离失败: {e}", err=True)
            raise typer.Exit(code=1) from e

        unique_speakers = {
            seg.speaker
            for seg in doc.segments
            if seg.speaker and seg.speaker != "UNKNOWN"
        }
        speakers_str = ", ".join(sorted(unique_speakers))
        typer.echo(f"  识别到 {len(unique_speakers)} 位说话人: {speakers_str}")

    # Step 3: douyin-script
    typer.echo(f"[3/3] 生成解说稿 (provider: {sc_provider})")
    try:
        script = await generate_douyin_script(
            doc,
            title=title,
            provider_name=sc_provider,
            settings=settings,
            target_words=target_words,
        )
        write_markdown(output, script)
    except ValueError as e:
        typer.echo(f"生成失败: {e}", err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.echo(f"生成失败 (LLM 错误): {e}", err=True)
        raise typer.Exit(code=1) from e

    typer.echo("\n✅ 流水线完成!")
    typer.echo(f"  输出: {output}")
    typer.echo(f"  字数: {len(script)}")
