"""Step: 音频文件 → Transcript JSON。

通过外部 speech-transcriber CLI 完成语音转文字。
不在此项目内直接调用腾讯云 ASR / COS SDK。
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from podlator.steps.io import write_transcript
from podlator.steps.models import (
    TranscriptDocument,
    TranscriptProviderMeta,
    TranscriptSegmentModel,
    TranscriptSource,
)


async def transcribe_audio(
    audio_path: Path,
    *,
    provider_name: str = "tencent_cloud",
    speech_transcriber_project_dir: str | None = None,
) -> TranscriptDocument:
    """调用外部 speech-transcriber CLI 完成语音转文字。

    Args:
        audio_path: 音频文件路径。
        provider_name: speech-transcriber provider 名称。
        speech_transcriber_project_dir: speech-transcriber 项目目录。
            如果为 None，则使用默认路径。

    Returns:
        TranscriptDocument。

    Raises:
        FileNotFoundError: 音频文件或 speech-transcriber 项目不存在。
        RuntimeError: speech-transcriber CLI 返回非 0 exit code。
        ValueError: stdout 不是合法 JSON 或缺少必要字段。
    """
    if not audio_path.exists():
        raise FileNotFoundError(f"音频文件不存在: {audio_path}")

    if speech_transcriber_project_dir is None:
        speech_transcriber_project_dir = (
            "/Users/mac/Project_Personal/speech-transcriber"
        )

    project_dir = Path(speech_transcriber_project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"speech-transcriber 项目目录不存在: {project_dir}")

    # 构造命令（uv run --project <dir> speech-transcriber ...）
    cmd = [
        "uv",
        "run",
        "--project",
        str(project_dir),
        "speech-transcriber",
        "transcribe",
        str(audio_path),
        "--provider",
        provider_name,
        "--output",
        "json",
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        stderr_text = stderr.decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(
            f"speech-transcriber 返回非 0 exit code ({process.returncode}):\n"
            f"命令: {' '.join(cmd)}\n"
            f"stderr: {stderr_text}"
        )

    stdout_text = stdout.decode("utf-8", errors="replace")

    # speech-transcriber 输出的是 TranscriptResult.model_dump_json()
    try:
        raw = json.loads(stdout_text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"speech-transcriber stdout 不是合法 JSON: {e}\n"
            f"stdout 前 500 字符: {stdout_text[:500]}"
        ) from e

    if "text" not in raw or "segments" not in raw:
        raise ValueError(
            f"speech-transcriber stdout 缺少必要字段 (text, segments):\n"
            f"stdout: {stdout_text[:500]}"
        )

    # 映射 TranscriptResult → TranscriptDocument
    segments = [
        TranscriptSegmentModel(
            index=i,
            start=seg.get("start", 0.0),
            end=seg.get("end", 0.0),
            text=seg.get("text", ""),
            speaker=seg.get("speaker"),
            confidence=seg.get("confidence"),
        )
        for i, seg in enumerate(raw.get("segments", []))
    ]

    doc = TranscriptDocument(
        source=TranscriptSource(
            audio_path=str(audio_path),
            duration_seconds=raw.get("duration_seconds"),
        ),
        provider=TranscriptProviderMeta(
            name=raw.get("provider", provider_name),
            cost_usd=raw.get("metadata", {}).get("cost_usd", 0.0),
        ),
        text=raw.get("text", ""),
        segments=segments,
    )
    return doc


async def transcribe_to_file(
    audio_path: Path,
    output_path: Path,
    *,
    provider_name: str = "tencent_cloud",
    speech_transcriber_project_dir: str | None = None,
) -> TranscriptDocument:
    """转写音频并直接写入 Transcript JSON 文件。

    Args:
        audio_path: 音频文件路径。
        output_path: 输出 JSON 路径。
        provider_name: speech-transcriber provider 名称。
        speech_transcriber_project_dir: speech-transcriber 项目目录。

    Returns:
        TranscriptDocument。
    """
    doc = await transcribe_audio(
        audio_path,
        provider_name=provider_name,
        speech_transcriber_project_dir=speech_transcriber_project_dir,
    )
    write_transcript(output_path, doc)
    return doc
