"""Pipeline 中间产物归档测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from podlator.artifacts import ArtifactRecorder, record_node_artifacts
from podlator.graph.nodes._base import node


def test_artifact_recorder_writes_ordered_files_and_log(tmp_path: Path) -> None:
    """download_audio 完成后，归档音频副本、音频信息和详细日志。"""
    audio_path = tmp_path / "source.mp3"
    audio_path.write_bytes(b"fake mp3")
    state = {
        "task_id": "task-001",
        "source_url": "https://www.youtube.com/watch?v=abc",
    }
    patch = {
        "audio_path": str(audio_path),
        "audio_format": "mp3",
        "audio_size_bytes": 8,
    }

    recorder = ArtifactRecorder(data_dir=tmp_path / "data")
    written = recorder.record_node_completed(
        node_name="download_audio",
        state=state,
        patch=patch,
        duration_ms=12.5,
    )

    artifact_dir = tmp_path / "data" / "artifacts" / "task-001"
    assert artifact_dir.is_dir()
    assert (artifact_dir / "03_audio.mp3").read_bytes() == b"fake mp3"

    audio_info = json.loads((artifact_dir / "03_audio.json").read_text())
    assert audio_info["source_url"] == "https://www.youtube.com/watch?v=abc"
    assert audio_info["audio_path"] == str(audio_path)
    assert audio_info["artifact_audio_path"].endswith("03_audio.mp3")

    log_lines = (artifact_dir / "00_pipeline.log.jsonl").read_text().splitlines()
    assert len(log_lines) == 1
    log_event = json.loads(log_lines[0])
    assert log_event["event"] == "node_completed"
    assert log_event["node"] == "download_audio"
    assert log_event["duration_ms"] == 12.5
    assert "03_audio.json" in log_event["artifact_files"]
    assert written


def test_artifact_recorder_writes_transcript_and_chapters(tmp_path: Path) -> None:
    """转写和章节产物同时保留机器可读 JSON 与便于排查的文本/Markdown。"""
    state = {"task_id": "task-002", "source_url": "https://example.com/video"}
    recorder = ArtifactRecorder(data_dir=tmp_path / "data")

    recorder.record_node_completed(
        node_name="transcribe",
        state=state,
        patch={
            "transcript_text": "Hello world",
            "transcript_segments": [
                {
                    "text": "Hello world",
                    "start": 0.0,
                    "end": 1.2,
                    "speaker": "SPEAKER_00",
                    "confidence": 0.97,
                }
            ],
            "stt_provider": "deepgram",
            "has_diarization": True,
        },
        duration_ms=20.0,
    )
    recorder.record_node_completed(
        node_name="chapter_split",
        state={**state, "transcript_text": "Hello world"},
        patch={
            "chapters": [
                {
                    "index": 0,
                    "title": "开场",
                    "start": 0.0,
                    "end": 1.2,
                    "segment_indices": [0],
                    "summary_zh": "",
                }
            ]
        },
        duration_ms=30.0,
    )
    recorder.record_node_completed(
        node_name="summarize_chapters",
        state=state,
        patch={
            "chapters": [
                {
                    "index": 0,
                    "title": "开场",
                    "start": 0.0,
                    "end": 1.2,
                    "segment_indices": [0],
                    "summary_zh": "中文摘要",
                }
            ],
            "chapter_summaries": ["中文摘要"],
        },
        duration_ms=40.0,
    )

    artifact_dir = tmp_path / "data" / "artifacts" / "task-002"
    assert (artifact_dir / "04_transcript.txt").read_text() == "Hello world"
    transcript_json = json.loads((artifact_dir / "04_transcript.json").read_text())
    assert transcript_json["stt_provider"] == "deepgram"
    assert transcript_json["segments"][0]["speaker"] == "SPEAKER_00"
    assert "## 0. 开场" in (artifact_dir / "05_chapters.md").read_text()
    chapters_json = json.loads((artifact_dir / "05_chapters.json").read_text())
    assert chapters_json["chapters"][0]["title"] == "开场"
    assert "中文摘要" in (artifact_dir / "06_chapter_summaries.md").read_text()
    summary_json = json.loads((artifact_dir / "06_chapter_summaries.json").read_text())
    assert summary_json["chapters"][0]["summary_zh"] == "中文摘要"


@pytest.mark.asyncio
async def test_node_decorator_records_artifacts_after_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """节点装饰器成功返回 patch 后，自动触发归档。"""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    @node("transcribe")
    async def fake_node(_state: dict[str, object]) -> dict[str, object]:
        return {"transcript_text": "hello", "transcript_segments": []}

    result = await fake_node({"task_id": "decorated-task"})

    assert result["transcript_text"] == "hello"
    assert (
        tmp_path / "data" / "artifacts" / "decorated-task" / "04_transcript.txt"
    ).read_text() == "hello"


def test_record_node_artifacts_logs_errors_without_breaking_node(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """归档失败不能让业务节点失败，但必须写入节点日志。"""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    record_node_artifacts(
        node_name="unknown_node",
        state={"task_id": "task-003"},
        patch={"unexpected": object()},
        duration_ms=1.0,
    )

    artifact_dir = tmp_path / "data" / "artifacts" / "task-003"
    assert (artifact_dir / "00_pipeline.log.jsonl").exists()
