# Speech Transcriber Service Design

> Superseded on 2026-05-26: the user changed the integration direction from
> HTTP service to CLI invocation. The implemented project is
> `/Users/yangzhuoran/program/speech-transcriber`, and its current source of
> truth is `README.md` plus `docs/AI_USAGE.md` in that project. Do not use this
> document as an implementation plan unless the user explicitly asks to return
> to HTTP.

## Background

Podlator currently supports Tencent Cloud ASR inside its own STT provider layer. That implementation works for Podlator, but it is coupled to Podlator's state models, configuration, logging, and pipeline lifecycle.

The new requirement is to reuse Tencent Cloud speech-to-text in other business systems. The reusable boundary should be an HTTP service with stable API contracts. Tencent Cloud ASR is the first provider. A local model provider may be added later without changing external callers.

## Goals

- Create a new standalone project under `~/program/speech-transcriber`.
- Expose speech-to-text through HTTP APIs.
- Hide Tencent Cloud ASR and COS details behind a provider abstraction.
- Keep the external API stable when switching from Tencent Cloud to a local model.
- Provide detailed tests and AI-readable documentation for future integrations.
- Let Podlator call the new service over HTTP instead of directly calling Tencent Cloud.

## Non-Goals

- No Web UI in the first version.
- No authentication in the first version unless deployed beyond local/private trusted networks.
- No distributed queue, Redis, or multi-machine orchestration in the first version.
- No local Whisper implementation in the first version, only an interface prepared for it.
- No provider-specific fields in the public HTTP response unless placed under `metadata`.

## Recommended Architecture

The service should be built as a FastAPI application with a clean core/provider boundary.

```text
speech-transcriber
  ├── HTTP API layer
  ├── Job orchestration layer
  ├── Transcriber interface
  ├── TencentCloudTranscriber implementation
  ├── SQLite job store
  ├── Local file storage
  ├── CLI/dev utilities
  ├── Tests
  └── Documentation
```

The HTTP layer should not contain Tencent Cloud logic. It should validate requests, create jobs, expose job status, and serialize results. Provider-specific behavior belongs in provider implementations.

## Core Interface

The internal provider interface should look conceptually like this:

```python
class Transcriber:
    async def transcribe(
        self,
        audio: AudioInput,
        options: TranscribeOptions,
    ) -> TranscriptResult:
        ...
```

The shared result model should include:

- `text`: full transcript text.
- `segments`: timestamped transcript segments.
- `provider`: provider name, such as `tencent_cloud`.
- `duration_seconds`: audio duration if available.
- `has_diarization`: whether speaker labels are present.
- `metadata`: provider-specific diagnostics that callers should not depend on for core behavior.

Segment shape:

```json
{
  "start": 0.0,
  "end": 3.2,
  "text": "Example transcript text.",
  "speaker": "SPEAKER_0",
  "confidence": null
}
```

## Tencent Cloud Provider Flow

The first provider is `TencentCloudTranscriber`.

```text
audio input
  -> store audio locally
  -> upload to Tencent COS
  -> generate presigned GET URL
  -> call Tencent ASR CreateRecTask
  -> poll DescribeTaskStatus until success/failure/timeout
  -> parse ResultDetail or fallback Result text
  -> delete temporary COS object
  -> return TranscriptResult
```

Tencent Cloud task states should be normalized into internal job states. Provider failures should be converted into service-level error records with a retryable flag where possible.

## HTTP API

Speech recognition should be modeled as an asynchronous job. Long audio should not hold a single request open until completion.

### Create Transcription

```http
POST /v1/transcriptions
```

Supported input modes:

- `multipart/form-data` with an uploaded audio file.
- JSON body with `audio_url`.

Recommended common fields:

```json
{
  "audio_url": "https://example.com/audio.mp3",
  "language": "en",
  "diarize": true,
  "provider": "tencent_cloud"
}
```

Response:

```json
{
  "job_id": "uuid",
  "status": "queued"
}
```

### Get Transcription

```http
GET /v1/transcriptions/{job_id}
```

Completed response:

```json
{
  "job_id": "uuid",
  "status": "completed",
  "provider": "tencent_cloud",
  "text": "...",
  "segments": [],
  "duration_seconds": 864.02,
  "has_diarization": true,
  "error": null,
  "metadata": {}
}
```

Failed response:

```json
{
  "job_id": "uuid",
  "status": "failed",
  "provider": "tencent_cloud",
  "text": null,
  "segments": [],
  "duration_seconds": null,
  "has_diarization": false,
  "error": {
    "code": "provider_error",
    "message": "ASR task failed",
    "retryable": false
  },
  "metadata": {}
}
```

### Other Endpoints

- `GET /health`: health check.
- `GET /v1/transcriptions`: optional job list for development and operations.
- `DELETE /v1/transcriptions/{job_id}`: optional cleanup endpoint.

## Job Model

Use SQLite for first-version persistence. A job should record:

- `id`
- `status`: `queued`, `running`, `completed`, `failed`, `cancelled`
- `provider`
- `input_type`: `upload` or `url`
- `audio_path` or `audio_url`
- `result_json`
- `error_json`
- `created_at`, `updated_at`, `started_at`, `completed_at`

The first version can run jobs in FastAPI background tasks. If concurrency or reliability needs grow, the orchestration layer can be replaced by a queue without changing the HTTP contract.

## Podlator Integration

Podlator should switch from direct Tencent Cloud provider calls to HTTP service calls.

```text
Podlator transcribe node
  -> POST /v1/transcriptions with audio.mp3
  -> poll GET /v1/transcriptions/{job_id}
  -> map HTTP result to PodlatorState
```

Podlator configuration can become:

```env
STT_PROVIDER=http
STT_SERVICE_BASE_URL=http://localhost:8010
STT_SERVICE_TIMEOUT_SECONDS=10800
STT_SERVICE_POLL_INTERVAL_SECONDS=3
```

After that change, Podlator no longer needs Tencent Cloud ASR or COS credentials. Those credentials belong only to the speech-transcriber service.

## Testing Strategy

Unit tests:

- Tencent COS upload, presign, and cleanup behavior with fake clients.
- Tencent ASR request construction.
- Tencent ASR polling for pending, success, failed, unknown status, timeout.
- Tencent result parsing from `ResultDetail`.
- Tencent result parsing fallback from plain `Result`.
- Provider factory behavior.
- Error normalization.

API tests:

- Create job with uploaded file.
- Create job with `audio_url`.
- Query queued/running/completed/failed jobs.
- Reject missing audio input.
- Reject unsupported provider.
- Reject unsupported file type if file validation is enabled.
- Return 404 for unknown job ID.

Integration tests:

- FastAPI app + temporary SQLite + fake Tencent provider.
- End-to-end create job, execute fake provider, query completed result.

Smoke tests:

- Gated by `RUN_SMOKE=1`.
- Use real Tencent Cloud credentials and a short fixture audio file.
- Verify COS upload, ASR task completion, result parsing, and COS cleanup.

## Documentation Requirements

The new project should include documentation optimized for both humans and coding agents:

```text
docs/
  ├── AI_USAGE.md
  ├── API.md
  ├── CONFIGURATION.md
  ├── DEVELOPMENT.md
  ├── PROVIDER_INTERFACE.md
  └── PODLATOR_INTEGRATION.md
```

`docs/AI_USAGE.md` should be the main entry point for future AI agents. It should explain:

- What the service does.
- How to start it locally.
- Required environment variables.
- HTTP API examples with curl and Python.
- Response schemas.
- Error model.
- How other projects should call it.
- How to add a new provider.
- Which tests to run before claiming completion.
- A clear warning not to bypass the HTTP service by calling Tencent Cloud directly from consumer projects.

## First Version Scope

Build:

- FastAPI app.
- Async transcription job API.
- SQLite job store.
- Local audio file storage.
- Tencent Cloud ASR + COS provider.
- Tests with fake Tencent/COS clients.
- Gated real Tencent smoke test.
- Documentation listed above.
- Minimal CLI/dev command only if it helps run or inspect the service locally.

Defer:

- Auth.
- Web UI.
- Redis or external queues.
- Webhook callbacks.
- Local Whisper provider.
- Multi-tenant billing or quota management.

## Open Decisions

- Whether the first HTTP implementation should execute jobs through FastAPI `BackgroundTasks` or an in-process worker loop. Recommendation: start with `BackgroundTasks`, but keep job orchestration isolated behind a small service object.
- Whether uploaded audio files should be retained after completion. Recommendation: keep them locally during development and add configurable retention cleanup later.
- Whether `provider` should be request-selectable or service-configured only. Recommendation: allow request-level provider but default from service config.
