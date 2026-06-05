"""CLI Tool LLM Provider — 通过本机 claude -p / codex exec 调用强模型。

实现策略：
- 复用 transcribe.py 的 asyncio.create_subprocess_exec 范式
- cwd=mkdtemp() 隔离项目上下文（防止 CLAUDE.md 污染 prompt）
- asyncio.wait_for 超时保护
- 失败抛 ProviderError，由上层 step 决定降级策略

CLI 约定（经实际测试验证）：
- Claude：claude -p "<user>" --system-prompt "<system>" --model <id>
  --output-format json → 解析 stdout JSON .result / .total_cost_usd / .usage
- Codex：codex exec --cd <tmp> --skip-git-repo-check
  --sandbox read-only --ephemeral -o <out.txt>
  prompt 通过 stdin 传入（不是位置参数！）
  ChatGPT 账号不指定 -m 默认 gpt-5.5
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

from podlator.errors import ProviderError
from podlator.logging import get_logger
from podlator.providers.llm.base import LLMProvider, LLMResult

if TYPE_CHECKING:
    from podlator.config import Settings

logger = get_logger(__name__)


class CLIToolProvider(LLMProvider):
    """通过本机 CLI 工具（claude -p / codex exec）调用强模型。

    使用会员 OAuth 认证（不设 API key 环境变量），
    在临时空目录中运行以隔离项目上下文。
    """

    def __init__(self, settings: Settings, backend: str) -> None:
        """初始化 CLI Tool Provider。

        Args:
            settings: 应用配置。
            backend: "claude" 或 "codex"。
        """
        self._settings = settings
        self._backend = backend

        if backend == "claude":
            self._model = settings.cli_tool_claude_model
        elif backend == "codex":
            self._model = settings.cli_tool_codex_model
        else:
            raise ProviderError(
                backend,
                f"不支持的 CLI backend: {backend}",
                retryable=False,
            )

        self._timeout_s = settings.cli_tool_timeout_s

    # ------------------------------------------------------------------
    # LLMProvider 接口
    # ------------------------------------------------------------------

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 0,
    ) -> LLMResult:
        """通过 CLI 子进程调用模型。"""
        if self._backend == "claude":
            return await self._complete_via_claude(
                prompt, system=system, temperature=temperature, max_tokens=max_tokens
            )
        return await self._complete_via_codex(
            prompt, system=system, temperature=temperature, max_tokens=max_tokens
        )

    # ------------------------------------------------------------------
    # Claude CLI 路径
    # ------------------------------------------------------------------

    async def _complete_via_claude(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 0,
    ) -> LLMResult:
        """通过 claude -p 调用。"""
        log = logger.bind(provider="claude_cli", model=self._model)

        # 在临时空目录中运行（隔离 CLAUDE.md / 项目上下文）
        tmp_dir = tempfile.mkdtemp(prefix="podlator_claude_")

        cmd = [
            "claude",
            "-p",
            prompt,
            "--model",
            self._model,
            "--output-format",
            "json",
        ]
        if system:
            cmd.extend(["--system-prompt", system])
        if max_tokens:
            cmd.extend(["--max-tokens", str(max_tokens)])

        log.debug(
            "cli_spawning",
            backend="claude",
            model=self._model,
            cmd=" ".join(cmd[:6]) + " ...",
            cwd=tmp_dir,
            timeout_s=self._timeout_s,
        )

        start = time.monotonic()
        try:
            process = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=tmp_dir,
                ),
                timeout=self._timeout_s,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self._timeout_s,
            )
            duration_ms = (time.monotonic() - start) * 1000
        except TimeoutError:
            duration_ms = (time.monotonic() - start) * 1000
            log.error(
                "cli_timeout",
                backend="claude",
                timeout_s=self._timeout_s,
                duration_ms=duration_ms,
            )
            self._cleanup_tmp(tmp_dir)
            raise ProviderError(
                "claude_cli",
                f"子进程超时（{self._timeout_s}s）",
                retryable=True,
            )
        finally:
            self._cleanup_tmp(tmp_dir)

        stderr_text = stderr.decode("utf-8", errors="replace") if stderr else ""

        if process.returncode != 0:
            log.error(
                "cli_nonzero_exit",
                backend="claude",
                returncode=process.returncode,
                stderr=stderr_text[:500],
                duration_ms=duration_ms,
            )
            raise ProviderError(
                "claude_cli",
                f"claude 非 0 exit ({process.returncode}): "
                f"{stderr_text[:300]}",
                retryable=True,
            )

        stdout_text = stdout.decode("utf-8", errors="replace") if stdout else ""

        # 解析 JSON 输出
        try:
            result_json = json.loads(stdout_text)
        except json.JSONDecodeError as e:
            log.error(
                "cli_bad_json",
                backend="claude",
                stdout=stdout_text[:500],
                duration_ms=duration_ms,
            )
            raise ProviderError(
                "claude_cli",
                f"claude stdout 不是合法 JSON: {e}\n"
                f"stdout 前 500 字符: {stdout_text[:500]}",
                retryable=False,
            ) from e

        content = result_json.get("result", "")
        if not content:
            log.error(
                "cli_empty_result",
                backend="claude",
                stdout=stdout_text[:500],
                duration_ms=duration_ms,
            )
            raise ProviderError(
                "claude_cli",
                "claude 返回了空结果",
                retryable=False,
            )

        # 提取 token / cost
        usage = result_json.get("usage", {})
        tokens_in = usage.get("input_tokens", 0)
        tokens_out = usage.get("output_tokens", 0)
        cost_usd = result_json.get("total_cost_usd", 0.0)

        log.info(
            "llm_completed",
            provider="claude_cli",
            model=self._model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            duration_ms=duration_ms,
        )

        return LLMResult(
            content=content.strip(),
            model=self._model,
            provider_name="claude_cli",
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_ms=duration_ms,
            cost_usd=cost_usd,
        )

    # ------------------------------------------------------------------
    # Codex CLI 路径
    # ------------------------------------------------------------------

    async def _complete_via_codex(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 0,
    ) -> LLMResult:
        """通过 codex exec 调用。

        codex CLI v0.137 实际约定（经终端验证）：
        - prompt 必须通过 stdin 传入（不是位置参数）
        - ChatGPT 账号不指定 -m 默认 gpt-5.5
        - -o 文件在 --sandbox read-only 内也能写入
        - --cd 切换工作目录实现上下文隔离
        """
        log = logger.bind(provider="codex_cli", model=self._model or "default")

        tmp_dir = tempfile.mkdtemp(prefix="podlator_codex_")
        output_file = os.path.join(tmp_dir, "output.txt")

        # codex 没有独立的 --system-prompt，合并 system + user
        combined_prompt = prompt
        if system:
            combined_prompt = f"{system}\n\n---\n\n{prompt}"

        cmd = [
            "codex",
            "exec",
            "--cd",
            tmp_dir,
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--ephemeral",
            "-o",
            output_file,
        ]
        # 只有配置了模型才传 -m，否则用 codex 默认（ChatGPT 账号可用）
        if self._model:
            cmd.extend(["-m", self._model])

        log.debug(
            "cli_spawning",
            backend="codex",
            model=self._model or "default",
            cmd=" ".join(cmd),
            cwd=tmp_dir,
            timeout_s=self._timeout_s,
        )

        start = time.monotonic()
        try:
            process = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=tmp_dir,
                ),
                timeout=self._timeout_s,
            )

            # prompt 通过 stdin 传入
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=combined_prompt.encode("utf-8")),
                timeout=self._timeout_s,
            )
            duration_ms = (time.monotonic() - start) * 1000

            stderr_text = stderr.decode("utf-8", errors="replace") if stderr else ""

            if process.returncode != 0:
                log.error(
                    "cli_nonzero_exit",
                    backend="codex",
                    returncode=process.returncode,
                    stderr=stderr_text[:500],
                    duration_ms=duration_ms,
                )
                raise ProviderError(
                    "codex_cli",
                    f"codex 非 0 exit ({process.returncode}): "
                    f"{stderr_text[:300]}",
                    retryable=True,
                )

            # 读取 -o 输出文件（必须在 finally 清理前读取）
            try:
                content = Path(output_file).read_text(encoding="utf-8").strip()
            except FileNotFoundError:
                log.error(
                    "cli_missing_output",
                    backend="codex",
                    output_file=output_file,
                    duration_ms=duration_ms,
                )
                raise ProviderError(
                    "codex_cli",
                    f"codex 输出文件不存在: {output_file}",
                    retryable=False,
                )

            if not content:
                log.error(
                    "cli_empty_result",
                    backend="codex",
                    duration_ms=duration_ms,
                )
                raise ProviderError(
                    "codex_cli",
                    "codex 返回了空结果",
                    retryable=False,
                )

            # ChatGPT 会员用量走 agentic 额度，CLI 不输出详细 cost
            log.info(
                "llm_completed",
                provider="codex_cli",
                model=self._model or "default",
                tokens_in=0,
                tokens_out=0,
                cost_usd=0.0,
                note="ChatGPT 会员，用量走 agentic 额度",
                duration_ms=duration_ms,
            )

            return LLMResult(
                content=content,
                model=self._model or "codex_default",
                provider_name="codex_cli",
                tokens_in=0,
                tokens_out=0,
                duration_ms=duration_ms,
                cost_usd=0.0,
            )

        except TimeoutError:
            duration_ms = (time.monotonic() - start) * 1000
            log.error(
                "cli_timeout",
                backend="codex",
                timeout_s=self._timeout_s,
                duration_ms=duration_ms,
            )
            raise ProviderError(
                "codex_cli",
                f"子进程超时（{self._timeout_s}s）",
                retryable=True,
            )
        finally:
            self._cleanup_tmp(tmp_dir)

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _cleanup_tmp(tmp_dir: str) -> None:
        """清理临时目录（忽略错误）。"""
        try:
            import shutil

            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass
