"""Unit tests for CLIToolProvider (mock subprocess).

覆盖：
- claude_cli 成功路径：解析 JSON 取 result/cost/usage
- codex_cli 成功路径：读 -o 输出文件
- 非零退出 → ProviderError
- 超时 → ProviderError(retryable=True)
- 坏 JSON / 空输出 → 明确报错
- cwd 隔离：断言子进程使用临时目录而非仓库根
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from podlator.errors import ProviderError


def _make_settings(**overrides):
    """创建测试用 Settings。"""
    from podlator.config import Settings

    defaults = {
        "cli_tool_claude_model": "claude-sonnet-4-6",
        "cli_tool_codex_model": "gpt-5",
        "cli_tool_reasoning_effort": "high",
        "cli_tool_timeout_s": 30,
    }
    defaults.update(overrides)

    # 用 model_construct 跳过 .env 文件加载
    settings = Settings.model_construct(**defaults)
    return settings


# ── Claude CLI 路径 ──


class TestClaudeCLI:
    """claude -p CLI provider 测试。"""

    @pytest.mark.asyncio
    async def test_success_parses_json_result(self) -> None:
        """成功路径：claude 返回合法 JSON，解析 result/cost/usage。"""
        settings = _make_settings()

        expected_result = "这是一篇约6000字的解说稿..."
        expected_cost = 0.15
        expected_usage = {"input_tokens": 5000, "output_tokens": 3000}

        claude_output = json.dumps(
            {
                "result": expected_result,
                "total_cost_usd": expected_cost,
                "usage": expected_usage,
            }
        )

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(claude_output.encode(), b""))

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ) as mock_spawn:
            from podlator.providers.llm.cli_tool import CLIToolProvider

            provider = CLIToolProvider(settings, backend="claude")
            result = await provider.complete(
                prompt="写一篇解说稿",
                system="你是科技解说写手",
            )

        assert result.content == expected_result
        assert result.cost_usd == expected_cost
        assert result.tokens_in == expected_usage["input_tokens"]
        assert result.tokens_out == expected_usage["output_tokens"]
        assert result.provider_name == "claude_cli"
        assert result.model == "claude-sonnet-4-6"

        # 验证子进程调用参数
        mock_spawn.assert_called_once()
        cmd_args = mock_spawn.call_args[0]
        assert cmd_args[0] == "claude"
        assert "-p" in cmd_args
        assert "--output-format" in cmd_args
        assert "json" in cmd_args

    @pytest.mark.asyncio
    async def test_cwd_isolation_uses_temp_dir(self) -> None:
        """cwd 隔离：子进程在临时目录中运行，不是仓库根。"""
        settings = _make_settings()

        claude_output = json.dumps(
            {
                "result": "test output",
                "total_cost_usd": 0.01,
                "usage": {"input_tokens": 100, "output_tokens": 50},
            }
        )

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(claude_output.encode(), b""))

        repo_root = str(Path(__file__).parent.parent.parent.parent.parent)

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ) as mock_spawn:
            from podlator.providers.llm.cli_tool import CLIToolProvider

            provider = CLIToolProvider(settings, backend="claude")
            await provider.complete(prompt="test")

        # 验证 cwd 不是仓库根
        cwd = mock_spawn.call_args[1].get("cwd", "")
        assert cwd != repo_root
        assert cwd != os.getcwd()
        assert "/tmp/" in cwd or "podlator_claude_" in cwd or "Temp" in cwd, (
            f"cwd 应该是临时目录，实际: {cwd}"
        )

    @pytest.mark.asyncio
    async def test_nonzero_exit_raises_provider_error(self) -> None:
        """非零退出 → ProviderError(retryable=True)。"""
        settings = _make_settings()

        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(
            return_value=(b"", b"Error: authentication failed")
        )

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            from podlator.providers.llm.cli_tool import CLIToolProvider

            provider = CLIToolProvider(settings, backend="claude")
            with pytest.raises(ProviderError) as exc:
                await provider.complete(prompt="test")

            assert exc.value.provider == "claude_cli"
            assert exc.value.retryable is True
            assert "非 0 exit" in str(exc.value)

    @pytest.mark.asyncio
    async def test_timeout_raises_provider_error_retryable(self) -> None:
        """超时 → ProviderError(retryable=True)。"""
        settings = _make_settings(cli_tool_timeout_s=1)

        async def slow_communicate():
            await asyncio.sleep(10)
            return b"", b""

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = slow_communicate

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            from podlator.providers.llm.cli_tool import CLIToolProvider

            provider = CLIToolProvider(settings, backend="claude")
            with pytest.raises(ProviderError) as exc:
                await provider.complete(prompt="test")

            assert exc.value.provider == "claude_cli"
            assert exc.value.retryable is True
            assert "超时" in str(exc.value)

    @pytest.mark.asyncio
    async def test_bad_json_raises_provider_error(self) -> None:
        """坏 JSON → ProviderError(retryable=False)。"""
        settings = _make_settings()

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"not valid json {{{", b""))

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            from podlator.providers.llm.cli_tool import CLIToolProvider

            provider = CLIToolProvider(settings, backend="claude")
            with pytest.raises(ProviderError) as exc:
                await provider.complete(prompt="test")

            assert exc.value.retryable is False
            assert "不是合法 JSON" in str(exc.value)

    @pytest.mark.asyncio
    async def test_empty_result_raises_provider_error(self) -> None:
        """空 result → ProviderError。"""
        settings = _make_settings()

        claude_output = json.dumps(
            {
                "result": "",
                "total_cost_usd": 0.0,
                "usage": {},
            }
        )

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(claude_output.encode(), b""))

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            from podlator.providers.llm.cli_tool import CLIToolProvider

            provider = CLIToolProvider(settings, backend="claude")
            with pytest.raises(ProviderError) as exc:
                await provider.complete(prompt="test")

            assert "空结果" in str(exc.value)

    @pytest.mark.asyncio
    async def test_passes_system_prompt(self) -> None:
        """验证 --system-prompt 参数正确传递。"""
        settings = _make_settings()

        claude_output = json.dumps(
            {
                "result": "ok",
                "total_cost_usd": 0.0,
                "usage": {},
            }
        )

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(claude_output.encode(), b""))

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ) as mock_spawn:
            from podlator.providers.llm.cli_tool import CLIToolProvider

            provider = CLIToolProvider(settings, backend="claude")
            await provider.complete(
                prompt="user text",
                system="你是专业写手",
            )

        cmd_args = mock_spawn.call_args[0]
        assert "--system-prompt" in cmd_args
        system_idx = list(cmd_args).index("--system-prompt")
        assert cmd_args[system_idx + 1] == "你是专业写手"


# ── Codex CLI 路径 ──


class TestCodexCLI:
    """codex exec CLI provider 测试。"""

    def _make_codex_process(
        self, output_content: str, returncode: int = 0, stderr: str = ""
    ):
        """创建 mock codex 子进程并预设输出文件。"""

        mock_process = AsyncMock()
        mock_process.returncode = returncode
        mock_process.communicate = AsyncMock(return_value=(b"", stderr.encode()))

        # 我们需要拦截 subprocess 调用以写入输出文件
        # 策略：在 mock_spawn 的 side_effect 中写入文件
        return mock_process

    @pytest.mark.asyncio
    async def test_success_reads_output_file(self) -> None:
        """成功路径：codex 执行成功，从 -o 文件读取输出。"""
        settings = _make_settings()

        expected_output = "这是一篇由 GPT-5 生成的解说稿"

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        async def fake_spawn(*args, **kwargs):
            # 从参数中提取 -o 文件路径并写入内容
            nonlocal expected_output
            cmd = list(args)
            if "-o" in cmd:
                idx = cmd.index("-o")
                output_path = cmd[idx + 1]
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(output_path).write_text(expected_output, encoding="utf-8")
            return mock_process

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=fake_spawn,
        ):
            from podlator.providers.llm.cli_tool import CLIToolProvider

            provider = CLIToolProvider(settings, backend="codex")
            result = await provider.complete(
                prompt="写一篇解说稿",
                system="你是科技解说写手",
            )

        assert result.content == expected_output
        assert result.provider_name == "codex_cli"
        assert result.model == "gpt-5"

    @pytest.mark.asyncio
    async def test_cwd_isolation_uses_temp_dir(self) -> None:
        """cwd 隔离：子进程在临时目录中运行。"""
        settings = _make_settings()

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        repo_root = str(Path(__file__).parent.parent.parent.parent.parent)

        async def fake_spawn(*args, **kwargs):
            cmd = list(args)
            if "-o" in cmd:
                idx = cmd.index("-o")
                output_path = cmd[idx + 1]
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(output_path).write_text("test output", encoding="utf-8")
            return mock_process

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=fake_spawn,
        ) as mock_spawn:
            from podlator.providers.llm.cli_tool import CLIToolProvider

            provider = CLIToolProvider(settings, backend="codex")
            await provider.complete(prompt="test")

        cwd = mock_spawn.call_args[1].get("cwd", "")
        assert cwd != repo_root
        assert "/tmp/" in cwd or "podlator_codex_" in cwd or "Temp" in cwd, (
            f"cwd 应该是临时目录，实际: {cwd}"
        )

    @pytest.mark.asyncio
    async def test_nonzero_exit_raises_provider_error(self) -> None:
        """非零退出 → ProviderError(retryable=True)。"""
        settings = _make_settings()

        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(
            return_value=(b"", b"Error: model not available")
        )

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            from podlator.providers.llm.cli_tool import CLIToolProvider

            provider = CLIToolProvider(settings, backend="codex")
            with pytest.raises(ProviderError) as exc:
                await provider.complete(prompt="test")

            assert exc.value.provider == "codex_cli"
            assert exc.value.retryable is True

    @pytest.mark.asyncio
    async def test_timeout_raises_provider_error_retryable(self) -> None:
        """超时 → ProviderError(retryable=True)。"""
        settings = _make_settings(cli_tool_timeout_s=1)

        async def slow_communicate(**kwargs):  # noqa: ARG001
            await asyncio.sleep(10)
            return b"", b""

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = slow_communicate

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            from podlator.providers.llm.cli_tool import CLIToolProvider

            provider = CLIToolProvider(settings, backend="codex")
            with pytest.raises(ProviderError) as exc:
                await provider.complete(prompt="test")

            assert exc.value.retryable is True

    @pytest.mark.asyncio
    async def test_missing_output_file_raises_provider_error(self) -> None:
        """输出文件不存在 → ProviderError。"""
        settings = _make_settings()

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        # 不创建输出文件
        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            from podlator.providers.llm.cli_tool import CLIToolProvider

            provider = CLIToolProvider(settings, backend="codex")
            with pytest.raises(ProviderError) as exc:
                await provider.complete(prompt="test")

            assert "输出文件不存在" in str(exc.value)

    @pytest.mark.asyncio
    async def test_combines_system_and_user_prompt(self) -> None:
        """codex 没有独立 --system-prompt，system+user 应合并。"""
        settings = _make_settings()

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        async def fake_spawn(*args, **kwargs):
            cmd = list(args)
            if "-o" in cmd:
                idx = cmd.index("-o")
                output_path = cmd[idx + 1]
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(output_path).write_text("merged output", encoding="utf-8")
            return mock_process

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=fake_spawn,
        ):
            from podlator.providers.llm.cli_tool import CLIToolProvider

            provider = CLIToolProvider(settings, backend="codex")
            await provider.complete(
                prompt="用户 prompt",
                system="你是系统指令",
            )

        # system+user 合并后通过 stdin 传入（communicate input）
        input_bytes = mock_process.communicate.call_args[1]["input"]
        input_text = input_bytes.decode("utf-8")
        assert "你是系统指令" in input_text
        assert "用户 prompt" in input_text

    @pytest.mark.asyncio
    async def test_cost_unavailable_is_zero(self) -> None:
        """codex 无法获取 cost 时置 0 并记录日志。"""
        settings = _make_settings()

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(b"", b"some normal stderr without usage json")
        )

        async def fake_spawn(*args, **kwargs):
            cmd = list(args)
            if "-o" in cmd:
                idx = cmd.index("-o")
                output_path = cmd[idx + 1]
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(output_path).write_text("output content", encoding="utf-8")
            return mock_process

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=fake_spawn,
        ):
            from podlator.providers.llm.cli_tool import CLIToolProvider

            provider = CLIToolProvider(settings, backend="codex")
            result = await provider.complete(prompt="test")

        assert result.cost_usd == 0.0
        assert result.tokens_in == 0
        assert result.tokens_out == 0


# ── 通用测试 ──


class TestCLIToolProviderGeneral:
    """通用测试：不合法 backend、参数传递等。"""

    def test_invalid_backend_raises(self) -> None:
        """不支持的 backend → ProviderError。"""
        settings = _make_settings()

        from podlator.providers.llm.cli_tool import CLIToolProvider

        with pytest.raises(ProviderError, match="不支持的 CLI backend"):
            CLIToolProvider(settings, backend="unsupported")
