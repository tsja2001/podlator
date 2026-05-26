# Speech Transcriber Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> Superseded on 2026-05-26: the user changed the implementation target from
> HTTP service to CLI invocation. The implemented project is
> `/Users/yangzhuoran/program/speech-transcriber`. Use that project's
> `README.md`, `AGENTS.md`, and `docs/AI_USAGE.md` as the source of truth.

**Goal:** Build a standalone HTTP speech-to-text service at `~/program/speech-transcriber` with Tencent Cloud ASR as the first provider.

**Architecture:** FastAPI exposes asynchronous transcription jobs. The API layer calls a job service, which stores job state in SQLite and delegates provider work through a `Transcriber` interface. Tencent Cloud COS/ASR details stay inside `TencentCloudTranscriber`; consumers call HTTP only.

**Tech Stack:** Python 3.12, FastAPI, Pydantic Settings, SQLite via `aiosqlite`, httpx tests, pytest, Tencent Cloud SDK, qcloud-cos.

---

## File Structure

Create a new project at `/Users/yangzhuoran/program/speech-transcriber`.

- `pyproject.toml`: package metadata, dependencies, pytest/ruff/mypy config.
- `.env.example`: documented configuration.
- `README.md`: human quick start.
- `AGENTS.md`: future AI instructions.
- `src/speech_transcriber/config.py`: settings loaded from `.env`.
- `src/speech_transcriber/models.py`: public request/result/job models.
- `src/speech_transcriber/errors.py`: typed service/provider errors.
- `src/speech_transcriber/providers/base.py`: `Transcriber` protocol.
- `src/speech_transcriber/providers/tencent_cloud.py`: Tencent COS + ASR provider.
- `src/speech_transcriber/providers/factory.py`: provider selection.
- `src/speech_transcriber/storage/files.py`: local audio storage.
- `src/speech_transcriber/storage/jobs.py`: SQLite job store.
- `src/speech_transcriber/service.py`: job orchestration.
- `src/speech_transcriber/api.py`: FastAPI routes.
- `src/speech_transcriber/main.py`: app factory and ASGI app.
- `tests/`: unit/API/integration/smoke tests.
- `docs/AI_USAGE.md`: primary AI-consumable integration guide.
- `docs/API.md`, `docs/CONFIGURATION.md`, `docs/DEVELOPMENT.md`, `docs/PROVIDER_INTERFACE.md`, `docs/PODLATOR_INTEGRATION.md`: detailed docs.

## Tasks

### Task 1: Project Skeleton

- [ ] Create project directory and pyproject.
- [ ] Add package directories and empty `__init__.py` files.
- [ ] Add `.env.example`, `README.md`, and `AGENTS.md`.
- [ ] Run `uv sync` to create the environment.

### Task 2: Core Models and Errors

- [ ] Write tests for `TranscriptSegment`, `TranscriptResult`, and job response serialization.
- [ ] Verify tests fail because models do not exist.
- [ ] Implement models and service errors.
- [ ] Run model tests and verify they pass.

### Task 3: Tencent Result Parsing

- [ ] Write tests for parsing Tencent `ResultDetail`, timestamped `Result`, plain text fallback, and empty result.
- [ ] Verify parser tests fail.
- [ ] Implement parser functions inside the Tencent provider module.
- [ ] Run parser tests and verify they pass.

### Task 4: Tencent Provider

- [ ] Write tests using fake COS and ASR clients for upload, task creation, polling success, failed task, timeout, and cleanup.
- [ ] Verify provider tests fail.
- [ ] Implement `TencentCloudTranscriber`.
- [ ] Run provider tests and verify they pass.

### Task 5: Storage

- [ ] Write tests for local file storage and SQLite job lifecycle.
- [ ] Verify storage tests fail.
- [ ] Implement file storage and job store.
- [ ] Run storage tests and verify they pass.

### Task 6: Job Service

- [ ] Write tests for creating upload jobs, running jobs to completion, and failed provider behavior.
- [ ] Verify service tests fail.
- [ ] Implement job orchestration.
- [ ] Run service tests and verify they pass.

### Task 7: HTTP API

- [ ] Write API tests for health check, file upload job creation, URL job creation, job query, missing audio rejection, unsupported provider rejection, and unknown job ID.
- [ ] Verify API tests fail.
- [ ] Implement FastAPI routes.
- [ ] Run API tests and verify they pass.

### Task 8: Documentation

- [ ] Write AI and human documentation.
- [ ] Include curl examples, Python examples, environment variables, error model, testing commands, and Podlator integration notes.
- [ ] Review docs for stale names and contradictions.

### Task 9: Verification

- [ ] Run `uv run pytest`.
- [ ] Run `uv run ruff check .`.
- [ ] Run `uv run mypy src`.
- [ ] Optionally run smoke test with `RUN_SMOKE=1` and the provided audio file when Tencent credentials are configured.
