"""Pipeline 中间产物归档。"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from podlator.config import Settings
from podlator.logging import get_logger

logger = get_logger(__name__)


class ArtifactRecorder:
    """把每个节点的关键输入/输出写入任务级 artifacts 目录。

    目录结构类似 JS 项目里的 `dist/<task-id>/debug`：保留机器可读 JSON，
    同时写一份人能直接打开排查的 txt/md 文件。
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def record_node_completed(
        self,
        *,
        node_name: str,
        state: dict[str, Any],
        patch: dict[str, Any],
        duration_ms: float,
    ) -> list[Path]:
        """记录节点成功产物，返回本次写入的文件列表。"""
        artifact_dir = self._artifact_dir(state)
        written: list[Path] = []

        if node_name == "fetch_metadata":
            written.extend(self._write_fetch_metadata(artifact_dir, state, patch))
        elif node_name == "download_audio":
            written.extend(self._write_audio(artifact_dir, state, patch))
        elif node_name == "transcribe":
            written.extend(self._write_transcript(artifact_dir, patch, prefix="04"))
        elif node_name == "diarize":
            written.extend(
                self._write_transcript(artifact_dir, patch, prefix="04_diarized")
            )
        elif node_name == "chapter_split":
            written.extend(
                self._write_chapters(
                    artifact_dir, patch, prefix="05", basename="chapters"
                )
            )
        elif node_name == "summarize_chapters":
            written.extend(
                self._write_chapters(
                    artifact_dir, patch, prefix="06", basename="chapter_summaries"
                )
            )
        elif node_name == "polish_final":
            written.extend(self._write_brief(artifact_dir, patch, prefix="07"))
        elif node_name == "export_markdown":
            written.extend(self._write_export(artifact_dir, patch, prefix="08"))

        self._append_log(
            artifact_dir,
            {
                "event": "node_completed",
                "node": node_name,
                "duration_ms": duration_ms,
                "produced": list(patch.keys()),
                "artifact_files": [p.name for p in written],
                "summary": _patch_summary(patch),
            },
        )
        return written

    def record_node_failed(
        self,
        *,
        node_name: str,
        state: dict[str, Any],
        error: BaseException,
        duration_ms: float,
    ) -> None:
        """记录节点失败事件，便于和最后一个产物对齐。"""
        artifact_dir = self._artifact_dir(state)
        self._append_log(
            artifact_dir,
            {
                "event": "node_failed",
                "node": node_name,
                "duration_ms": duration_ms,
                "error_type": type(error).__name__,
                "error_msg": str(error),
            },
        )

    def _artifact_dir(self, state: dict[str, Any]) -> Path:
        task_id = str(state.get("task_id") or "unknown")
        artifact_dir = self._data_dir / "artifacts" / task_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        return artifact_dir

    def _write_fetch_metadata(
        self,
        artifact_dir: Path,
        state: dict[str, Any],
        patch: dict[str, Any],
    ) -> list[Path]:
        source_file = artifact_dir / "01_source.json"
        metadata_file = artifact_dir / "02_metadata.json"
        self._write_json(
            source_file,
            {
                "task_id": state.get("task_id"),
                "source_url": state.get("source_url"),
                "captured_at": _now_iso(),
            },
        )
        self._write_json(
            metadata_file, {"source_url": state.get("source_url"), **patch}
        )
        return [source_file, metadata_file]

    def _write_audio(
        self,
        artifact_dir: Path,
        state: dict[str, Any],
        patch: dict[str, Any],
    ) -> list[Path]:
        audio_path = Path(str(patch.get("audio_path", "")))
        suffix = audio_path.suffix or f".{patch.get('audio_format', 'audio')}"
        artifact_audio = artifact_dir / f"03_audio{suffix}"
        written: list[Path] = []

        if audio_path.exists():
            self._copy_file(audio_path, artifact_audio)
            written.append(artifact_audio)

        info_file = artifact_dir / "03_audio.json"
        self._write_json(
            info_file,
            {
                "source_url": state.get("source_url"),
                "audio_path": str(audio_path),
                "artifact_audio_path": str(artifact_audio),
                "audio_format": patch.get("audio_format"),
                "audio_size_bytes": patch.get("audio_size_bytes"),
            },
        )
        written.append(info_file)
        return written

    def _write_transcript(
        self,
        artifact_dir: Path,
        patch: dict[str, Any],
        *,
        prefix: str,
    ) -> list[Path]:
        text_file = artifact_dir / f"{prefix}_transcript.txt"
        json_file = artifact_dir / f"{prefix}_transcript.json"
        transcript_text = str(patch.get("transcript_text", ""))
        segments = patch.get("transcript_segments", [])

        text_file.write_text(transcript_text, encoding="utf-8")
        self._write_json(
            json_file,
            {
                "transcript_text": transcript_text,
                "segments": segments,
                "stt_provider": patch.get("stt_provider"),
                "has_diarization": patch.get("has_diarization"),
            },
        )
        return [text_file, json_file]

    def _write_chapters(
        self,
        artifact_dir: Path,
        patch: dict[str, Any],
        *,
        prefix: str,
        basename: str,
    ) -> list[Path]:
        chapters = patch.get("chapters", [])
        json_file = artifact_dir / f"{prefix}_{basename}.json"
        md_file = artifact_dir / f"{prefix}_{basename}.md"

        self._write_json(json_file, {"chapters": chapters})
        md_file.write_text(_chapters_to_markdown(chapters), encoding="utf-8")
        return [json_file, md_file]

    def _write_brief(
        self,
        artifact_dir: Path,
        patch: dict[str, Any],
        *,
        prefix: str,
    ) -> list[Path]:
        brief_file = artifact_dir / f"{prefix}_polished_brief.md"
        brief_file.write_text(str(patch.get("brief_markdown", "")), encoding="utf-8")
        return [brief_file]

    def _write_export(
        self,
        artifact_dir: Path,
        patch: dict[str, Any],
        *,
        prefix: str,
    ) -> list[Path]:
        export_file = artifact_dir / f"{prefix}_export.json"
        self._write_json(export_file, patch)
        return [export_file]

    def _append_log(self, artifact_dir: Path, event: dict[str, Any]) -> None:
        log_file = artifact_dir / "00_pipeline.log.jsonl"
        payload = {"timestamp": _now_iso(), **event}
        with log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )

    def _copy_file(self, source: Path, target: Path) -> None:
        try:
            if target.exists():
                target.unlink()
            target.hardlink_to(source)
        except OSError:
            shutil.copy2(source, target)


def record_node_artifacts(
    *,
    node_name: str,
    state: dict[str, Any],
    patch: dict[str, Any],
    duration_ms: float,
) -> None:
    """从节点装饰器调用；归档异常只记录日志，不影响业务节点结果。"""
    try:
        recorder = ArtifactRecorder(Settings().data_dir)
        written = recorder.record_node_completed(
            node_name=node_name,
            state=state,
            patch=patch,
            duration_ms=duration_ms,
        )
        logger.info(
            "artifacts_recorded",
            task_id=state.get("task_id", "unknown"),
            node=node_name,
            artifact_files=[str(path) for path in written],
        )
    except Exception as exc:  # pragma: no cover - defensive observability guard
        logger.warning(
            "artifact_recording_failed",
            task_id=state.get("task_id", "unknown"),
            node=node_name,
            error_type=type(exc).__name__,
            error_msg=str(exc),
        )


def record_node_failure_artifact(
    *,
    node_name: str,
    state: dict[str, Any],
    error: BaseException,
    duration_ms: float,
) -> None:
    """记录失败节点，失败时同样不能掩盖原始异常。"""
    try:
        ArtifactRecorder(Settings().data_dir).record_node_failed(
            node_name=node_name,
            state=state,
            error=error,
            duration_ms=duration_ms,
        )
    except Exception as exc:  # pragma: no cover - defensive observability guard
        logger.warning(
            "artifact_failure_recording_failed",
            task_id=state.get("task_id", "unknown"),
            node=node_name,
            error_type=type(exc).__name__,
            error_msg=str(exc),
        )


def _chapters_to_markdown(chapters: Any) -> str:
    if not isinstance(chapters, list):
        return ""

    lines: list[str] = []
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        index = chapter.get("index", "")
        title = chapter.get("title", "")
        start = chapter.get("start", "")
        end = chapter.get("end", "")
        summary = chapter.get("summary_zh", "")
        lines.extend(
            [
                f"## {index}. {title}",
                "",
                f"- start: {start}",
                f"- end: {end}",
                "",
                str(summary),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + ("\n" if lines else "")


def _patch_summary(patch: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    if "audio_path" in patch:
        summary["audio_path"] = patch.get("audio_path")
        summary["audio_size_bytes"] = patch.get("audio_size_bytes")
    if "transcript_text" in patch:
        summary["transcript_char_count"] = len(str(patch.get("transcript_text", "")))
    if "transcript_segments" in patch:
        segments = patch.get("transcript_segments")
        summary["transcript_segment_count"] = (
            len(segments) if isinstance(segments, list) else 0
        )
    if "chapters" in patch:
        chapters = patch.get("chapters")
        summary["chapter_count"] = len(chapters) if isinstance(chapters, list) else 0
    if "brief_markdown" in patch:
        summary["brief_char_count"] = len(str(patch.get("brief_markdown", "")))
    if "output_path" in patch:
        summary["output_path"] = patch.get("output_path")
    return summary


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
