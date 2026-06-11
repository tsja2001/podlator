"""Step: 口播稿程序化检查（零 LLM 成本）。

检查项：
- 中文字数 vs 目标（±10%）
- Markdown 标题残留（^#{1,6}\\s）
- Meta 文字（开头 200 字内命中「好的，」「以下是」「下面我们」「交给我」等模式）
- Speaker 标签残留（Speaker [A-Z] / 说话人[A-Z甲乙丙]）
- 句长分布（按 。！？切句；>40 字为长句，<15 字为短句）
- 互动词密度（词表见下，每 300 字次数）
- 截断探针（非空稿件结尾未落在 。！？…」"）等终止符 → 疑似被生成上限/输入截断）
"""

from __future__ import annotations

import re

from podlator.steps.models import LintStats, RevisionDirective

INTERACTION_WORDS = [
    "你想",
    "你看",
    "你猜",
    "说白了",
    "说实话",
    "说真的",
    "听明白了吧",
    "你听",
    "我认为",
    "我觉得",
    "对吧",
    "是不是",
]

META_PATTERNS = [
    re.compile(r"^好的[，,]"),
    re.compile(r"^以下是"),
    re.compile(r"^下面我们"),
    re.compile(r"交给我"),
    re.compile(r"^这是一篇"),
]

# 非空稿件结尾必须落在这组字符中的其中之一
SENTENCE_END_CHARS = frozenset("。！？…」\"')")


def _count_chinese_chars(text: str) -> int:
    """统计文本中中文字符数（含中文标点）。

    复用 douyin_script.py 中的逻辑。
    """
    count = 0
    for ch in text:
        if "一" <= ch <= "鿿" or "　" <= ch <= "〿" or "＀" <= ch <= "￯":
            count += 1
        elif ch in "，。！？；：''（）【】《》—…·":
            count += 1
    return count


def _split_sentences(text: str) -> list[str]:
    """按 。！？ 切句，过滤空串。"""
    return [s.strip() for s in re.split(r"[。！？]", text) if s.strip()]


def _count_interactions(text: str) -> int:
    """统计互动词出现总次数。"""
    total = 0
    for word in INTERACTION_WORDS:
        total += text.count(word)
    return total


def _detect_meta_opening(text: str) -> bool:
    """检测开头 200 字内是否命中 meta 模式。"""
    head = text[:200]
    for pat in META_PATTERNS:
        if pat.search(head):
            return True
    return False


def lint_script(
    script: str,
    *,
    target_words: int | None = None,
) -> tuple[LintStats, list[RevisionDirective]]:
    """对口播稿做程序化检查。

    Returns:
        (统计数据, 硬伤修订指令列表)。硬伤包括：Markdown 标题、meta 文字、
        speaker 标签、字数偏离 >10%。
    """
    directives: list[RevisionDirective] = []

    char_count = _count_chinese_chars(script)
    sentences = _split_sentences(script)
    sentence_count = len(sentences)

    # 句长分布
    long_count = sum(1 for s in sentences if _count_chinese_chars(s) > 40)
    short_count = sum(1 for s in sentences if _count_chinese_chars(s) < 15)
    long_sentence_ratio = long_count / sentence_count if sentence_count > 0 else 0.0
    short_sentence_ratio = short_count / sentence_count if sentence_count > 0 else 0.0

    # 互动词密度（每 300 字互动次数）
    interaction_total = _count_interactions(script)
    interaction_density = (
        interaction_total / (char_count / 300) if char_count > 0 else 0.0
    )

    # Markdown 标题残留
    markdown_heading_count = len(re.findall(r"^#{1,6}\s", script, re.MULTILINE))
    if markdown_heading_count > 0:
        directives.append(
            RevisionDirective(
                target="全稿",
                problem=f"检测到 {markdown_heading_count} 处 Markdown 标题残留",
                instruction=(
                    "删除全部 Markdown 标题行，"
                    "改用口语过渡词衔接（'你看''接下来''聊到这里'）"
                ),
            )
        )

    # Meta 文字
    meta_text_detected = _detect_meta_opening(script)
    if meta_text_detected:
        directives.append(
            RevisionDirective(
                target="开头",
                problem="稿件开头检测到 AI 引导语（meta 文字）",
                instruction="删除开头的引导语，直接从标题和正文开始",
            )
        )

    # Speaker 标签残留
    speaker_label_count = len(re.findall(r"Speaker\s+[A-Z]|说话人[A-Z甲乙丙]", script))
    if speaker_label_count > 0:
        directives.append(
            RevisionDirective(
                target="全稿",
                problem=f"检测到 {speaker_label_count} 处 Speaker 标签残留",
                instruction=(
                    "把 Speaker A/B 等标签改写为自然称呼（人名或'主持人''嘉宾'）"
                ),
            )
        )

    # 截断探针 —— 非空稿件结尾未落在终止符
    truncation_suspected = False
    if char_count > 0:
        stripped_end = script.rstrip()
        if stripped_end and stripped_end[-1] not in SENTENCE_END_CHARS:
            truncation_suspected = True
            directives.append(
                RevisionDirective(
                    target="末段",
                    problem='稿件疑似被截断（未以 。！？…」" 等终止符收尾）',
                    instruction=(
                        "定位末段排查生成上限/输入截断，"
                        "**重新生成而非续写**（续写会破坏结尾收束）"
                    ),
                )
            )

    # 字数检查
    word_count_target = target_words
    word_count_ok: bool | None = None
    if target_words is not None:
        lower = int(target_words * 0.9)
        upper = int(target_words * 1.1)
        word_count_ok = lower <= char_count <= upper
        if not word_count_ok:
            if char_count < lower:
                directives.append(
                    RevisionDirective(
                        target="字数不足的主题段落",
                        problem=(f"当前 {char_count} 字低于目标下限 {lower} 字"),
                        instruction=(
                            "挑写得最薄的主题定点扩写"
                            "（举例/背景/点评），"
                            "禁止在结尾后追加新段落"
                        ),
                    )
                )
            else:
                directives.append(
                    RevisionDirective(
                        target="全稿",
                        problem=(f"当前 {char_count} 字超出目标上限 {upper} 字"),
                        instruction="删减重复表达和离题段落",
                    )
                )

    stats = LintStats(
        char_count=char_count,
        sentence_count=sentence_count,
        long_sentence_ratio=round(long_sentence_ratio, 4),
        short_sentence_ratio=round(short_sentence_ratio, 4),
        interaction_density=round(interaction_density, 4),
        markdown_heading_count=markdown_heading_count,
        meta_text_detected=meta_text_detected,
        speaker_label_count=speaker_label_count,
        truncation_suspected=truncation_suspected,
        word_count_target=word_count_target,
        word_count_ok=word_count_ok,
    )

    return stats, directives
