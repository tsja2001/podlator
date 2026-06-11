"""M5.0 Phase 4 Smoke — 验证 DeepSeek finish_reason 真实行为 + reasoning token 假设。

预估费用：< ¥1（两次小量调用）。

用途：
1. 证明我们对真实 API 正确读到了 finish_reason = "length"
2. 验证 50 分片在新 max_tokens 下是否真的不截断
3. 探查 v4-flash 是否有 reasoning token
"""

from __future__ import annotations

import os

import pytest

from podlator.config import Settings
from podlator.providers.llm.deepseek import DeepSeekProvider


@pytest.fixture
def provider() -> DeepSeekProvider:
    settings = Settings()
    return DeepSeekProvider(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
        max_tokens=settings.deepseek_max_tokens,  # 现在默认 32768
    )


@pytest.mark.skipif(
    not os.getenv("PODLATOR_RUN_SMOKE"), reason="PODLATOR_RUN_SMOKE=1 required"
)
@pytest.mark.asyncio
async def test_deepseek_truncation_detection_real(provider: DeepSeekProvider) -> None:
    """故意用极小 max_tokens 验证 finish_reason == 'length' 能被正确读取。

    预估费用：< ¥0.10（仅 64 token 输出）。
    """
    print("\n=== 测试 1: 极小 max_tokens 触发截断 ===")
    result = await provider.complete(
        "请用中文写一篇 500 字的文章，介绍人工智能的历史发展。"
        "要求：详细、完整、分章节。请开始：",
        max_tokens=64,
        temperature=0.3,
    )

    print(f"finish_reason: {result.finish_reason}")
    print(f"tokens_in: {result.tokens_in}")
    print(f"tokens_out: {result.tokens_out}")
    print(f"cost_usd: ${result.cost_usd}")
    print(f"content preview (前 100 字): {result.content[:100]}")

    assert result.finish_reason == "length", (
        f"Expected finish_reason='length' with max_tokens=64, "
        f"got '{result.finish_reason}'"
    )
    print("✅ 截断检测正确：finish_reason == 'length'")


@pytest.mark.skipif(
    not os.getenv("PODLATOR_RUN_SMOKE"), reason="PODLATOR_RUN_SMOKE=1 required"
)
@pytest.mark.asyncio
async def test_deepseek_50_shard_no_truncation_real(
    provider: DeepSeekProvider,
) -> None:
    """用 50 条 segment 的 assign-speakers 风格 prompt 验证不再截断。

    这是 M5.0 的核心假设：50 分片在 8192 token 上限下 finish_reason == "stop"。
    如果返回 "length"，说明 v4-flash 的 reasoning token 超出了预期。

    预估费用：< ¥0.50（50 条标注的输出约 2-3K token）。
    """
    print("\n=== 测试 2: 50 分片验证不截断 ===")

    # 构造 50 条模拟 segment 的 prompt
    segments_text = "\n".join(
        f"[{i * 5.0:.2f} - {(i + 1) * 5.0:.2f}] "
        f"index={i} speaker=None: This is segment number {i} containing some "
        f"technical discussion about artificial intelligence and its implications "
        f"for the future of technology and society."
        for i in range(50)
    )

    prompt = (
        "Here are transcript segments. "
        "For each segment, assign the most likely speaker label.\n\n"
        f"Segments:\n{segments_text}\n\n"
        'Output ONLY a JSON array with "index" and "speaker" for each segment:\n'
        '[{"index": 0, "speaker": "HOST"}, ...]'
    )

    result = await provider.complete(
        prompt,
        system="You are a speaker diarization assistant. "
        "Output ONLY a JSON array of objects with 'index' and 'speaker' fields.",
        temperature=0.2,
        max_tokens=8192,  # _SPEAKER_SHARD_MAX_TOKENS
    )

    print(f"finish_reason: {result.finish_reason}")
    print(f"tokens_in: {result.tokens_in}")
    print(f"tokens_out: {result.tokens_out}")
    print(f"cost_usd: ${result.cost_usd}")
    print(f"duration_ms: {result.duration_ms}")

    # 检查 usage 中是否包含 reasoning tokens（通过打印 usage 对象属性）
    try:
        # 尝试通过 token 分布判断：若 tokens_out 远超预期（如 >5K）
        # 可能是 reasoning token 计入
        ratio = result.tokens_in / max(1, result.tokens_out)
        print(f"tokens_in/tokens_out ratio: {ratio:.1f}")
        print("Note: 如果 tokens_out 远超 3K，可能 reasoning token 被计入")
    except Exception as e:
        print(f"解析 usage 细节失败: {e}")

    # 检查是否截断
    if result.finish_reason == "length":
        print(
            "⚠️  50 分片在 8192 max_tokens 下仍截断！"
            "v4-flash 可能消耗 reasoning token，"
            f"tokens_out={result.tokens_out}，"
            "建议调高 _SPEAKER_SHARD_MAX_TOKENS 到 tokens_out 的 2 倍"
        )
    elif result.finish_reason == "stop":
        print("✅ 50 分片在 8192 max_tokens 下不截断 — 假设成立")
    else:
        print(f"⚠️  意外的 finish_reason: {result.finish_reason}")

    # 验证 JSON 内容是否完整（最后一条 index 应为 49）
    import json

    content = result.content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        items = json.loads(content)
        max_index = max(item["index"] for item in items if "index" in item)
        print(f"共返回 {len(items)} 条标注，最大 index={max_index}")
        if max_index == 49:
            print("✅ 所有 50 条的标注完整（index 0–49）")
        else:
            print(f"⚠️  最大 index={max_index}，期望 49")
    except json.JSONDecodeError as e:
        print(f"⚠️  JSON 解析失败: {e}")
        print(f"content 前 200 字符: {content[:200]}")
        print(f"content 后 200 字符: {content[-200:]}")
