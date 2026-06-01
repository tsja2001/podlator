"""Unit tests for transcribe step (mock subprocess boundary)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from podlator.steps.transcribe import transcribe_audio, transcribe_to_file

SPEECH_TRANSCRIBER_JSON = json.dumps(
    {
        "text": "Hello world. This is a test.",
        "segments": [
            {
                "start": 0.0,
                "end": 2.5,
                "text": "Hello world.",
                "speaker": "SPEAKER_0",
                "confidence": None,
            },
            {
                "start": 2.5,
                "end": 5.0,
                "text": "This is a test.",
                "speaker": "SPEAKER_1",
                "confidence": None,
            },
        ],
        "provider": "tencent_cloud",
        "duration_seconds": 5.0,
        "has_diarization": True,
        "metadata": {},
    }
)


def _make_mock_process(returncode=0, stdout="", stderr=""):
    """创建 mock asyncio subprocess。"""
    mock = AsyncMock()
    mock.returncode = returncode
    mock.communicate = AsyncMock(return_value=(stdout.encode(), stderr.encode()))
    return mock


class TestTranscribeAudio:
    @pytest.mark.asyncio
    async def test_success(self, tmp_path: Path) -> None:
        """正常路径：CLI 返回合法 JSON，能映射为 TranscriptDocument。"""

        audio = tmp_path / "audio.mp3"
        audio.write_text("fake audio")

        mock_proc = _make_mock_process(returncode=0, stdout=SPEECH_TRANSCRIBER_JSON)

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
            return_value=mock_proc,
        ):
            doc = await transcribe_audio(
                audio,
                provider_name="tencent_cloud",
                speech_transcriber_project_dir=str(tmp_path),
            )

        assert doc.provider.name == "tencent_cloud"
        assert doc.text == "Hello world. This is a test."
        assert doc.source.duration_seconds == 5.0
        assert doc.source.audio_path == str(audio)
        assert len(doc.segments) == 2
        assert doc.segments[0].text == "Hello world."
        assert doc.segments[0].speaker == "SPEAKER_0"
        assert doc.segments[0].index == 0

    @pytest.mark.asyncio
    async def test_subprocess_args_correct(self, tmp_path: Path) -> None:
        """验证传给 speech-transcriber CLI 的参数正确。"""
        audio = tmp_path / "audio.mp3"
        audio.write_text("fake audio")

        mock_proc = _make_mock_process(returncode=0, stdout=SPEECH_TRANSCRIBER_JSON)

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
            return_value=mock_proc,
        ) as mock_exec:
            await transcribe_audio(
                audio,
                provider_name="tencent_cloud",
                speech_transcriber_project_dir=str(tmp_path),
            )

        call_args = mock_exec.call_args[0]
        assert call_args[0] == "uv"
        assert call_args[1] == "run"
        assert call_args[2] == "--project"
        assert call_args[3] == str(tmp_path)
        assert call_args[4] == "speech-transcriber"
        assert call_args[5] == "transcribe"
        assert call_args[6] == str(audio)
        assert "--provider" in call_args
        assert "tencent_cloud" in call_args
        assert "--output" in call_args
        assert "json" in call_args

    @pytest.mark.asyncio
    async def test_audio_not_found(self) -> None:
        """音频文件不存在时抛出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError, match="音频文件不存在"):
            await transcribe_audio(Path("/nonexistent.mp3"))

    @pytest.mark.asyncio
    async def test_cli_non_zero_exit(self, tmp_path: Path) -> None:
        """CLI 返回非 0 exit code 时抛出 RuntimeError。"""
        audio = tmp_path / "audio.mp3"
        audio.write_text("fake audio")

        mock_proc = _make_mock_process(returncode=1, stderr="Error: audio too short")

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
            return_value=mock_proc,
        ):
            with pytest.raises(RuntimeError, match="非 0 exit code"):
                await transcribe_audio(
                    audio,
                    speech_transcriber_project_dir=str(tmp_path),
                )

    @pytest.mark.asyncio
    async def test_invalid_json_stdout(self, tmp_path: Path) -> None:
        """stdout 不是合法 JSON 时抛出 ValueError。"""
        audio = tmp_path / "audio.mp3"
        audio.write_text("fake audio")

        mock_proc = _make_mock_process(returncode=0, stdout="not valid json!!!")

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
            return_value=mock_proc,
        ):
            with pytest.raises(ValueError, match="不是合法 JSON"):
                await transcribe_audio(
                    audio,
                    speech_transcriber_project_dir=str(tmp_path),
                )

    @pytest.mark.asyncio
    async def test_missing_required_fields(self, tmp_path: Path) -> None:
        """stdout JSON 缺少 text/segments 时抛出 ValueError。"""
        audio = tmp_path / "audio.mp3"
        audio.write_text("fake audio")

        mock_proc = _make_mock_process(returncode=0, stdout='{"provider": "x"}')

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
            return_value=mock_proc,
        ):
            with pytest.raises(ValueError, match="缺少必要字段"):
                await transcribe_audio(
                    audio,
                    speech_transcriber_project_dir=str(tmp_path),
                )


class TestTranscribeToFile:
    @pytest.mark.asyncio
    async def test_writes_transcript_json(self, tmp_path: Path) -> None:
        """验证 transcribe_to_file 写文件。"""
        audio = tmp_path / "audio.mp3"
        audio.write_text("fake audio")
        out = tmp_path / "transcript.json"

        mock_proc = _make_mock_process(returncode=0, stdout=SPEECH_TRANSCRIBER_JSON)

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
            return_value=mock_proc,
        ):
            doc = await transcribe_to_file(
                audio, out, speech_transcriber_project_dir=str(tmp_path)
            )

        assert out.exists()
        assert doc.text == "Hello world. This is a test."
