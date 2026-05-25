# 腾讯云 ASR 大模型版 + COS 接入开发文档

> 目标：把当前 Deepgram STT 替换为腾讯云语音识别录音文件识别，默认使用 `16k_zh_large` 大模型引擎；通过 COS 暂存音频并生成可下载 URL，解决腾讯云本地音频上传 5MB 限制。

## 1. 背景与约束

当前 Podlator 的 STT 抽象是 `STTProvider.transcribe(audio_path)`，现有实现是 Deepgram 直接上传本地音频并同步等待结果。腾讯云录音文件识别不是同步接口，而是：

1. 上传或提供音频 URL。
2. 调用 `CreateRecTask` 创建异步识别任务。
3. 调用 `DescribeTaskStatus` 轮询任务状态。
4. 成功后解析 `ResultDetail` / `Result` 为项目内的 `TranscriptSegment`。

腾讯云接口约束：

- 录音文件识别请求域名：`asr.tencentcloudapi.com`
- 任务提交接口：`CreateRecTask`
- 结果查询接口：`DescribeTaskStatus`
- 本地 `Data` 上传限制：原始音频数据不超过 5MB。
- URL 提交限制：音频时长不超过 5 小时，文件大小不超过 1GB。
- 识别结果保存 24 小时，`TaskId` 有效期 24 小时。
- 任务提交默认限频 20 次/秒，状态查询默认限频 50 次/秒。

参考：

- https://cloud.tencent.com/document/product/1093/37823
- https://cloud.tencent.com/document/product/1093/37822
- https://cloud.tencent.com/document/product/1093/52632
- https://cloud.tencent.com/document/product/436/65820
- https://cloud.tencent.com/document/product/436/35153

## 2. ASR 参数策略

默认使用用户指定的大模型版：

```text
EngineModelType=16k_zh_large
ChannelNum=1
ResTextFormat=2
SourceType=0
SpeakerDiarization=0
EmotionRecognition=0
EmotionalEnergy=0
FilterDirty=0
FilterPunc=0
FilterModal=0
ConvertNumMode=1
```

说明：

- `16k_zh_large` 是普方英大模型引擎，支持中文、英文和多种中文方言，适合中英混杂内容。
- `ResTextFormat=2` 返回带标点的词粒度详细结果，不使用增值版语义分段或口语转书面语。
- `SourceType=0` 表示使用音频 URL。真实播客普遍超过 5MB，不能依赖 `SourceType=1`。
- 默认不开说话人分离，避免误用可能不在预付费包里的能力。后续可通过配置开启 `SpeakerDiarization=1` 做真实账单验证。
- 不使用 `ResTextFormat=4/5`、情绪识别、角色分离等增值功能。

## 3. COS 接入方案

腾讯 ASR 要求 `Url` 是公网环境浏览器可下载地址。对私有 COS 桶，方案是：

1. 把本地音频上传到 COS。
2. 为该对象生成 `GET` 预签名 URL。
3. 把预签名 URL 作为 `CreateRecTask.Url`。
4. ASR 任务完成后，可选择删除 COS 临时对象。

COS Python SDK 推荐使用 `upload_file()` 高级接口，它会根据文件大小自动选择简单上传或分块上传，并支持断点续传。生成下载 URL 使用 `get_presigned_url(Method="GET", ...)`。

## 4. 需要用户提供的 COS 信息

必需：

```text
TENCENT_COS_BUCKET=你的完整桶名，例如 podlator-audio-1330315023
TENCENT_COS_REGION=桶所在地域，例如 ap-shanghai / ap-guangzhou
TENCENT_COS_SECRET_ID=具备 COS 权限的 SecretId
TENCENT_COS_SECRET_KEY=对应 SecretKey
TENCENT_COS_PREFIX=podlator/asr-audio
```

可选：

```text
TENCENT_COS_TOKEN=临时密钥 token；使用永久密钥时为空
TENCENT_COS_SCHEME=https
TENCENT_COS_PRESIGNED_EXPIRES_SECONDS=21600
TENCENT_COS_DELETE_AFTER_TRANSCRIBE=true
TENCENT_COS_STORAGE_CLASS=STANDARD
```

字段说明：

- `TENCENT_COS_BUCKET` 必须包含 APPID，格式是 `BucketName-APPID`。腾讯 SDK 文档说明 AppID 不再放到 `CosConfig`，而是放在 Bucket 参数里。
- `TENCENT_COS_REGION` 必须是 COS 存储桶地域，不一定等于 ASR 的 `Region`。
- `TENCENT_COS_PREFIX` 用于隔离临时音频，例如 `podlator/asr-audio/{task_id}/{filename}`。
- `TENCENT_COS_PRESIGNED_EXPIRES_SECONDS` 建议至少 6 小时，覆盖上传、ASR 拉取和最长 3 小时识别窗口。
- 建议使用 CAM 子账号密钥，不建议使用主账号永久密钥。

## 5. CAM 权限建议

如果使用 SDK 高级上传并在识别后删除临时音频，子账号至少需要：

```text
cos:PutObject
cos:GetObject
cos:DeleteObject
cos:InitiateMultipartUpload
cos:UploadPart
cos:CompleteMultipartUpload
cos:AbortMultipartUpload
cos:ListParts
cos:ListMultipartUploads
```

权限范围建议限制到指定 Bucket 和指定 prefix：

```text
qcs::cos:<region>:uid/<uin>:<bucket>/<prefix>/*
```

如果第一版不做删除，可暂时不授予 `cos:DeleteObject`。如果强制只上传小文件并不用高级上传，可只给 `cos:PutObject` / `cos:GetObject`，但这不适合播客长音频。

## 6. 新增配置项

```python
# Tencent ASR
tencent_app_id: str = ""
tencent_secret_id: str = ""
tencent_secret_key: str = ""
tencent_asr_region: str = "ap-shanghai"
tencent_asr_engine_model_type: str = "16k_zh_large"
tencent_asr_res_text_format: int = 2
tencent_asr_speaker_diarization: int = 0
tencent_asr_poll_interval_seconds: float = 3.0
tencent_asr_timeout_seconds: float = 10800.0

# Tencent COS
tencent_cos_bucket: str = ""
tencent_cos_region: str = ""
tencent_cos_secret_id: str = ""
tencent_cos_secret_key: str = ""
tencent_cos_token: str = ""
tencent_cos_prefix: str = "podlator/asr-audio"
tencent_cos_scheme: str = "https"
tencent_cos_presigned_expires_seconds: int = 21600
tencent_cos_delete_after_transcribe: bool = True
```

密钥关系：

- ASR 和 COS 都使用腾讯云访问密钥体系。
- 如果同一个子账号同时有 ASR 调用权限和 COS 指定桶权限，可以复用同一组 SecretId/SecretKey。
- 代码层建议保留 ASR 和 COS 两组配置项，便于后续用不同子账号做最小权限隔离。

## 7. 代码改动计划

### 7.1 依赖

新增：

```text
tencentcloud-sdk-python
cos-python-sdk-v5
```

备选：如果不想引入腾讯云 ASR SDK，可以用现有 `httpx` 自行实现 TC3-HMAC-SHA256 签名。但签名逻辑容易出错，第一版建议使用官方 SDK。

### 7.2 文件

新增：

- `src/podlator/providers/stt/tencent_cloud.py`
- `src/podlator/providers/cos.py` 或 `src/podlator/storage/cos_audio.py`
- `tests/unit/providers/stt/test_tencent_cloud.py`
- `tests/unit/test_tencent_cos_audio.py`
- `tests/fixtures/responses/tencent_asr_success.json`
- `tests/smoke/test_tencent_asr_real.py`

修改：

- `src/podlator/config.py`
- `src/podlator/providers/stt/__init__.py`
- `.env.example`
- `README.md`
- `docs/ARCHITECTURE.md`
- `CHANGELOG.md`

### 7.3 Provider 流程

```text
TencentCloudProvider.transcribe(audio_path)
  ├─ 校验文件存在
  ├─ upload audio to COS
  ├─ generate presigned GET URL
  ├─ CreateRecTask(SourceType=0, Url=presigned_url, EngineModelType=16k_zh_large, ...)
  ├─ poll DescribeTaskStatus(TaskId)
  │   ├─ Status=0 waiting: sleep
  │   ├─ Status=1 doing: sleep
  │   ├─ Status=2 success: parse result
  │   └─ Status=3 failed: raise ProviderError
  ├─ optionally delete COS object
  └─ return STTResult
```

### 7.4 结果解析

优先解析 `Data.ResultDetail`：

```text
FinalSentence -> TranscriptSegment.text
StartMs / EndMs -> start / end 秒
SpeakerId -> SPEAKER_{id}，仅当 SpeakerDiarization 开启且返回有效 speaker 时使用
```

如果 `ResultDetail` 为空，则回退解析 `Data.Result`：

- 能解析 `[0:0.020,0:2.380] 文本` 格式时生成带时间戳 segment。
- 不能解析时生成单个无时间戳或 0 起点 segment，并记录 warning。

### 7.5 成本记录

腾讯云使用预付费包，代码不估算美元成本：

```text
cost_usd=0.0
provider_name="tencent_cloud"
```

后续如果需要展示分钟消耗，可新增 `usage_seconds` 或在 artifact 中记录 `AudioDuration`，不要塞进 `cost_usd`。

## 8. 测试计划

单元测试：

- `test_transcribe_uploads_to_cos_and_submits_url_task`
- `test_transcribe_polls_until_success`
- `test_transcribe_raises_retryable_on_rate_limit`
- `test_transcribe_raises_non_retryable_on_failed_task`
- `test_transcribe_times_out`
- `test_parse_result_detail_to_segments`
- `test_parse_result_fallback_when_detail_missing`
- `test_factory_returns_tencent_cloud_provider`

Smoke 测试：

- 使用小于 5MB 的 fixture 音频，仍走 COS URL 路径。
- 通过环境变量开启：`PODLATOR_RUN_SMOKE=1`
- 必需环境变量：ASR + COS 全部配置。
- 测试只断言：任务成功、segments 非空、provider_name 为 `tencent_cloud`。

DoD：

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
```

## 9. 风险与开放点

- 预签名 URL 必须在腾讯 ASR 拉取音频时仍有效，过期时间不能太短。
- 私有桶 + 预签名 URL 理论上满足“公网可下载”，但需要 smoke 测试确认腾讯 ASR 服务能正常拉取。
- `16k_zh_large` 对纯英文播客的效果需要和 `16k_en_large` 做一次样本对比；用户已指定 `16k_zh_large`，第一版按此实现。
- 说话人分离先不开，避免误消耗非预付费包能力。后续可单独加一个验证任务。
- 当前项目的 `diarize` 节点在 `has_diarization=False` 时仍是占位逻辑，关闭腾讯说话人分离后，章节和摘要会没有 speaker 标签。这是可接受的第一版行为。
