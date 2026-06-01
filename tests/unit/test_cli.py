"""CLI 命令测试。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from podlator.cli import app

runner = CliRunner()


def test_version() -> None:
    """版本命令正常输出。"""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "podlator" in result.stdout


def test_run_help() -> None:
    """run 命令显示帮助。"""
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "URL" in result.stdout


def test_status_no_args(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """无参数 status 显示最近任务或暂无任务。"""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "暂无任务" in result.stdout


def test_status_specific_task(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """指定 task_id 查询 status，不存在的任务返回错误。"""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    result = runner.invoke(app, ["status", "nonexistent-id"])
    assert result.exit_code == 1
    assert "任务不存在" in result.stderr or "任务不存在" in result.stdout


def test_list_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """空任务列表正常输出。"""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "暂无任务" in result.stdout


def test_list_with_status_filter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """按状态过滤任务列表。"""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    result = runner.invoke(app, ["list", "--status", "completed"])
    assert result.exit_code == 0


def test_run_command_mock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run 命令触发 pipeline 执行（mock graph）。"""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {
        "task_id": "test-001",
        "source_url": "https://example.com/video",
        "title": "Mock Episode",
        "output_path": str(tmp_path / "output.md"),
        "total_cost_usd": 0.005,
        "duration_seconds": 30.0,
    }

    with patch("podlator.graph.builder.build_graph", return_value=mock_graph):
        result = runner.invoke(app, ["run", "https://example.com/video"])

    assert result.exit_code == 0
    assert "✅ 处理完成" in result.stdout
    assert "输出" in result.stdout or "简报" in result.stdout


# ── 文件转换型 Step CLI 测试 ──


class TestParseSrtCommand:
    def test_parse_srt_writes_transcript_json(self, tmp_path: Path) -> None:
        """parse-srt 能解析 SRT 并写 Transcript JSON。"""
        srt = tmp_path / "test.srt"
        srt.write_text(
            "1\n00:00:00,000 --> 00:00:05,000\nHello world.\n",
            encoding="utf-8",
        )
        out = tmp_path / "transcript.json"

        result = runner.invoke(app, ["parse-srt", str(srt), "-o", str(out)])
        assert result.exit_code == 0
        assert "字幕解析完成" in result.stdout
        assert out.exists()
        data = json.loads(out.read_text())
        assert len(data["segments"]) == 1
        assert data["provider"]["name"] == "srt"

    def test_parse_srt_file_not_found(self, tmp_path: Path) -> None:
        """SRT 文件不存在返回非 0 退出码（Typer exists=True 校验，exit 2）。"""
        out = tmp_path / "out.json"
        result = runner.invoke(
            app, ["parse-srt", str(tmp_path / "missing.srt"), "-o", str(out)]
        )
        assert result.exit_code != 0

    def test_parse_srt_help(self) -> None:
        """parse-srt --help 显示帮助。"""
        result = runner.invoke(app, ["parse-srt", "--help"])
        assert result.exit_code == 0
        assert "SRT" in result.stdout


class TestAssignSpeakersCommand:
    def test_assign_speakers_writes_transcript_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """assign-speakers 能读取 Transcript JSON 并写带 speaker 的输出。"""
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        # 准备输入
        from podlator.steps.io import write_transcript
        from podlator.steps.models import (
            TranscriptDocument,
            TranscriptProviderMeta,
            TranscriptSegmentModel,
            TranscriptSource,
        )

        doc = TranscriptDocument(
            source=TranscriptSource(title="Test"),
            provider=TranscriptProviderMeta(name="srt"),
            segments=[
                TranscriptSegmentModel(
                    index=0, start=0.0, end=5.0, text="Hi.", speaker=None
                ),
                TranscriptSegmentModel(
                    index=1, start=5.0, end=10.0, text="Hello.", speaker=None
                ),
            ],
        )
        in_path = tmp_path / "in.json"
        write_transcript(in_path, doc)
        out_path = tmp_path / "out.json"

        # mock LLM
        from podlator.providers.llm.base import LLMResult

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content=json.dumps(
                    [
                        {"index": 0, "speaker": "HOST"},
                        {"index": 1, "speaker": "GUEST"},
                    ]
                ),
                model="test",
                provider_name="deepseek",
                tokens_in=100,
                tokens_out=50,
                duration_ms=500,
                cost_usd=0.001,
            )
        )

        with patch(
            "podlator.steps.assign_speakers.get_llm_provider",
            return_value=mock_llm,
        ):
            result = runner.invoke(
                app, ["assign-speakers", str(in_path), "-o", str(out_path)]
            )

        assert result.exit_code == 0
        assert out_path.exists()
        data = json.loads(out_path.read_text())
        assert data["segments"][0]["speaker"] == "HOST"


class TestSplitCommand:
    def test_split_writes_chapters_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """split 能读取 Transcript JSON 并写 Chapters JSON。"""
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        from podlator.steps.io import write_transcript
        from podlator.steps.models import (
            TranscriptDocument,
            TranscriptProviderMeta,
            TranscriptSegmentModel,
            TranscriptSource,
        )

        doc = TranscriptDocument(
            source=TranscriptSource(title="Test", duration_seconds=20.0),
            provider=TranscriptProviderMeta(name="deepgram"),
            segments=[
                TranscriptSegmentModel(
                    index=i,
                    start=i * 10.0,
                    end=(i + 1) * 10.0,
                    text=f"Segment {i}.",
                    speaker="A",
                )
                for i in range(2)
            ],
        )
        in_path = tmp_path / "in.json"
        write_transcript(in_path, doc)
        out_path = tmp_path / "chapters.json"

        from podlator.providers.llm.base import LLMResult

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content=json.dumps([{"title": "开场", "start": 0.0, "end": 20.0}]),
                model="test",
                provider_name="deepseek",
                tokens_in=100,
                tokens_out=50,
                duration_ms=500,
                cost_usd=0.001,
            )
        )

        with patch(
            "podlator.steps.split_chapters.get_llm_provider",
            return_value=mock_llm,
        ):
            result = runner.invoke(app, ["split", str(in_path), "-o", str(out_path)])

        assert result.exit_code == 0
        assert out_path.exists()
        data = json.loads(out_path.read_text())
        assert len(data["chapters"]) == 1
        assert data["chapters"][0]["title"] == "开场"


class TestRenderCommand:
    def test_render_summary_writes_markdown(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """render --mode summary 能写 Markdown。"""
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        from podlator.steps.io import write_chapters, write_transcript
        from podlator.steps.models import (
            ChapterDocument,
            ChapterModel,
            TranscriptDocument,
            TranscriptProviderMeta,
            TranscriptSegmentModel,
            TranscriptSource,
        )

        transcript = TranscriptDocument(
            source=TranscriptSource(title="Test", duration_seconds=10.0),
            provider=TranscriptProviderMeta(name="deepgram"),
            segments=[
                TranscriptSegmentModel(
                    index=0, start=0.0, end=10.0, text="Hello.", speaker="A"
                )
            ],
        )
        chapters = ChapterDocument(
            chapters=[
                ChapterModel(
                    index=0,
                    title="开场",
                    start=0.0,
                    end=10.0,
                    segment_indices=[0],
                )
            ]
        )
        t_path = tmp_path / "transcript.json"
        c_path = tmp_path / "chapters.json"
        out_path = tmp_path / "output.md"
        write_transcript(t_path, transcript)
        write_chapters(c_path, chapters)

        from podlator.providers.llm.base import LLMResult

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content="开场摘要内容。",
                model="test",
                provider_name="deepseek",
                tokens_in=100,
                tokens_out=50,
                duration_ms=500,
                cost_usd=0.001,
            )
        )

        with patch(
            "podlator.steps.render_chinese.get_llm_provider",
            return_value=mock_llm,
        ):
            result = runner.invoke(
                app,
                [
                    "render",
                    str(t_path),
                    "--chapters",
                    str(c_path),
                    "-o",
                    str(out_path),
                    "--mode",
                    "summary",
                ],
            )

        assert result.exit_code == 0
        assert out_path.exists()
        content = out_path.read_text()
        assert "Test" in content

    def test_render_full_mode_writes_markdown(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """render --mode full 能走全文翻译。"""
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        from podlator.steps.io import write_chapters, write_transcript
        from podlator.steps.models import (
            ChapterDocument,
            ChapterModel,
            TranscriptDocument,
            TranscriptProviderMeta,
            TranscriptSegmentModel,
            TranscriptSource,
        )

        transcript = TranscriptDocument(
            source=TranscriptSource(title="Test", duration_seconds=10.0),
            provider=TranscriptProviderMeta(name="deepgram"),
            segments=[
                TranscriptSegmentModel(
                    index=0, start=0.0, end=10.0, text="Hello.", speaker="A"
                )
            ],
        )
        chapters = ChapterDocument(
            chapters=[
                ChapterModel(
                    index=0,
                    title="Ch1",
                    start=0.0,
                    end=10.0,
                    segment_indices=[0],
                )
            ]
        )
        t_path = tmp_path / "transcript.json"
        c_path = tmp_path / "chapters.json"
        out_path = tmp_path / "output.md"
        write_transcript(t_path, transcript)
        write_chapters(c_path, chapters)

        from podlator.providers.llm.base import LLMResult

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content="第一章全文翻译。",
                model="test",
                provider_name="deepseek",
                tokens_in=100,
                tokens_out=50,
                duration_ms=500,
                cost_usd=0.001,
            )
        )

        with patch(
            "podlator.steps.render_chinese.get_llm_provider",
            return_value=mock_llm,
        ):
            result = runner.invoke(
                app,
                [
                    "render",
                    str(t_path),
                    "--chapters",
                    str(c_path),
                    "-o",
                    str(out_path),
                    "--mode",
                    "full",
                ],
            )

        assert result.exit_code == 0
        assert "全文翻译" in out_path.read_text()


class TestPolishCommand:
    def test_polish_writes_markdown(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """polish 能读取草稿并写润色后的 Markdown。"""
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        draft = tmp_path / "draft.md"
        draft.write_text("# Hello\nWorld", encoding="utf-8")
        out_path = tmp_path / "polished.md"

        from podlator.providers.llm.base import LLMResult

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=LLMResult(
                content="# 你好\n世界",
                model="test",
                provider_name="claude",
                tokens_in=50,
                tokens_out=30,
                duration_ms=1000,
                cost_usd=0.005,
            )
        )

        with patch(
            "podlator.steps.polish.get_llm_provider",
            return_value=mock_llm,
        ):
            result = runner.invoke(app, ["polish", str(draft), "-o", str(out_path)])

        assert result.exit_code == 0
        assert out_path.exists()
        assert "你好" in out_path.read_text()


class TestMissingInputFileErrors:
    def test_assign_speakers_missing_file(self, tmp_path: Path) -> None:
        """缺少输入文件时返回非 0 退出码。"""
        result = runner.invoke(
            app,
            [
                "assign-speakers",
                str(tmp_path / "missing.json"),
                "-o",
                str(tmp_path / "out.json"),
            ],
        )
        assert result.exit_code != 0

    def test_split_missing_file(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "split",
                str(tmp_path / "missing.json"),
                "-o",
                str(tmp_path / "out.json"),
            ],
        )
        assert result.exit_code != 0

    def test_render_missing_file(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "render",
                str(tmp_path / "missing.json"),
                "--chapters",
                str(tmp_path / "missing_ch.json"),
                "-o",
                str(tmp_path / "out.md"),
            ],
        )
        assert result.exit_code != 0

    def test_polish_missing_file(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "polish",
                str(tmp_path / "missing.md"),
                "-o",
                str(tmp_path / "out.md"),
            ],
        )
        assert result.exit_code != 0
