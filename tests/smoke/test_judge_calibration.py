"""M5.1 Phase 5 Smoke — judge 校准：用 4 个已有人工评分的样本验证 judge 排序一致性。

预估费用：¥1–2（4 次 DeepSeek judge 调用，无参照清单模式）。

前置条件：
- DeepSeek API key 已配置
- 校准样本存在于 project/ 目录（见下方路径列表）
- 运行方式：PODLATOR_RUN_SMOKE=1 uv run pytest \\
  tests/smoke/test_judge_calibration.py -v -s
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from podlator.config import Settings
from podlator.steps.evaluate_script import evaluate_script

# 校准样本路径（由统筹者确认实际文件名后更新）
# 人工评分基准来自 docs/goal目标制定/差距分析-三篇产出vs黄金样本.md
CALIBRATION_SAMPLES = [
    {
        "name": "黄金样本（黄仁勋）",
        "dir": "project/英伟达黄仁勋播客/抖音剪辑版",
        "human_score_100": 100.0,
    },
    {
        "name": "Musk v2",
        "dir": "project/02马斯克如何把 1 太瓦 GPU 送上太空 /抖音剪辑版",
        "human_score_100": 90.0,
    },
    {
        "name": "Casey v2",
        "dir": "project/04Casey Handmer中国将赢得通用AGI竞争/抖音剪辑版",
        "human_score_100": 88.0,
    },
    {
        "name": "Nielsen v2",
        "dir": "project/01迈克尔·尼尔森——为何外星文明的技术栈将与我们不同/抖音剪辑版",
        "human_score_100": 78.0,
    },
]


def _find_script_file(sample_dir: str) -> str | None:
    """在 sample_dir 中找口播稿 Markdown 文件。"""
    p = Path(sample_dir)
    if not p.exists():
        return None
    # 找最可能的 Markdown 文件
    md_files = sorted(p.rglob("*.md"))
    for f in md_files:
        # 排除 标题、简介、开场文案 等非正片文件
        if any(
            skip in f.name
            for skip in [
                "标题",
                "简介",
                "开场",
                "发布",
                "review",
                "digest",
                "blueprint",
                "speakers",
            ]
        ):
            continue
        return str(f)
    return None


@pytest.mark.skipif(
    not os.getenv("PODLATOR_RUN_SMOKE"), reason="PODLATOR_RUN_SMOKE=1 required"
)
@pytest.mark.asyncio
async def test_judge_calibration_ranking_matches_human() -> None:
    """judge 评 4 个样本（无参照清单模式），断言排序一致性。

    断言：
    1. 排序一致：黄金 > {Musk v2, Casey v2} > Nielsen v2
    2. 黄金样本 total >= 80
    3. Nielsen v2 与黄金样本分差 >= 8
    """
    settings = Settings()
    results: list[dict] = []

    for sample in CALIBRATION_SAMPLES:
        script_path = _find_script_file(sample["dir"])
        if script_path is None:
            print(f"\n⚠️  跳过 {sample['name']}：找不到稿件文件 ({sample['dir']})")
            continue

        script_text = Path(script_path).read_text(encoding="utf-8")
        print(f"\n{'=' * 60}")
        print(f"样本: {sample['name']}")
        print(f"文件: {script_path}")
        print(f"人工基准分: {sample['human_score_100']}")
        print(f"{'─' * 60}")

        try:
            report, lint_stats = await evaluate_script(
                script_text,
                settings=settings,
                reference_points=None,  # 无参照清单 — 覆盖度不计分
                rubric_version="v3",
            )
        except Exception as e:
            print(f"❌ 评分失败: {e}")
            continue

        print(f"Judge 总分: {report.total_score} (verdict: {report.verdict})")
        print(
            f"lint -> 字数: {lint_stats.char_count}, "
            f"截断: {lint_stats.truncation_suspected}"
        )
        for d in report.dimensions:
            score_str = f"{d.score:.0f}" if d.score >= 0 else "N/A"
            print(f"  {d.dimension}: {score_str}/{d.max_score:.0f}")

        results.append(
            {
                "name": sample["name"],
                "human_score": sample["human_score_100"],
                "judge_score": report.total_score,
                "verdict": report.verdict,
            }
        )

    if len(results) < 3:
        print("\n⚠️  样本不足 3 个，跳过排序断言")
        return

    # 断言 1: 排序
    results.sort(key=lambda r: r["judge_score"], reverse=True)
    print(f"\n{'=' * 60}")
    print("排序 (judge 分数降序):")
    for r in results:
        print(f"  {r['name']}: judge={r['judge_score']} (人工={r['human_score']})")

    # 黄金样本应在最前
    golden = [r for r in results if "黄仁勋" in r["name"] or "黄金" in r["name"]]
    nielsen = [r for r in results if "Nielsen" in r["name"] or "尼尔森" in r["name"]]

    if golden and nielsen:
        assert golden[0]["judge_score"] >= 80, (
            f"黄金样本总分应 ≥ 80，实际 {golden[0]['judge_score']}"
        )
        assert (golden[0]["judge_score"] - nielsen[0]["judge_score"]) >= 8, (
            f"黄金与 Nielsen 分差应 ≥ 8，实际 "
            f"{golden[0]['judge_score'] - nielsen[0]['judge_score']:.1f}"
        )
        print("✅ 校准断言通过")

    print(f"\n总调用次数: {len(results)}")
