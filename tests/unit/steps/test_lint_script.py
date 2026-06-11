"""lint_script 单元测试（M5.1 Phase 2）。全部用构造文本，不读真实文件。"""

from __future__ import annotations

from podlator.steps.lint_script import lint_script


class TestLintDetection:
    """硬伤检测测试。"""

    def test_lint_detects_markdown_headers(self) -> None:
        """含 Markdown 标题的文本应检出对应指令。"""
        script = "## 一、开场\n\n这是一段正文。然后结束了。"
        stats, directives = lint_script(script)

        assert stats.markdown_heading_count >= 1
        md_dirs = [d for d in directives if "Markdown" in d.problem]
        assert len(md_dirs) >= 1

    def test_lint_detects_meta_opening(self) -> None:
        """以「好的，交给我了。」开头应检出 meta 文字。"""
        script = "好的，交给我了。接下来看看英伟达的股价表现。"
        stats, directives = lint_script(script)

        assert stats.meta_text_detected is True
        meta_dirs = [d for d in directives if "引导语" in d.problem]
        assert len(meta_dirs) >= 1

    def test_lint_detects_speaker_labels(self) -> None:
        """含 Speaker A: 的文本应检出标签残留。"""
        script = "Speaker A: 我认为这个观点很重要。Speaker B: 我同意。你好。"
        stats, directives = lint_script(script)

        assert stats.speaker_label_count >= 1
        spk_dirs = [d for d in directives if "Speaker" in d.problem]
        assert len(spk_dirs) >= 1


class TestLintWordCount:
    """字数检查测试。"""

    def test_lint_word_count_within_tolerance(self) -> None:
        """5700 字对目标 6000，应在 ±10% 容差内（5700 > 5400=6000*0.9）。"""
        # 构造约 5700 字的中文文本
        script = "你好" * 2850  # 2 * 2850 = 5700 字
        stats, _directives = lint_script(script, target_words=6000)

        assert stats.char_count == 5700
        assert stats.word_count_ok is True

    def test_lint_word_count_below_tolerance_yields_directive(self) -> None:
        """4000 字、目标 6000，应产出含「定点扩写」和「禁止在结尾后追加」的指令。"""
        script = "你好" * 2000  # 4000 字
        _stats, directives = lint_script(script, target_words=6000)

        below_dirs = [d for d in directives if d.target != "末段"]
        assert len(below_dirs) >= 1
        instr = below_dirs[0].instruction
        assert "定点扩写" in instr
        assert "禁止在结尾后追加" in instr


class TestLintSentenceStats:
    """句长分布与互动词测试。"""

    def test_lint_sentence_stats_on_constructed_text(self) -> None:
        """构造 2 长句 + 8 短句 → long_sentence_ratio 应为 0.2。"""
        # 短句（<15 字）：每个 "你好短句。" = 6 字
        short = ["你好短句。"] * 8
        # 长句（>40 字）：构造 44 个中文字符的句子（4 chars x 11 = 44 > 40）
        long_sent = "".join(["这是长句"] * 11) + "。"
        long_sent2 = "".join(["另外长句"] * 11) + "！"
        script = "".join(short) + long_sent + long_sent2

        stats, _directives = lint_script(script)

        assert stats.sentence_count > 0
        assert stats.long_sentence_ratio == 0.2  # 2 of 10
        assert stats.short_sentence_ratio == 0.8  # 8 of 10

    def test_lint_interaction_density(self) -> None:
        """600 字含 4 个互动词 → density 应为 2.0（4 / (600/300) = 2.0）。"""
        # 300 个"你好"（600 中文字）+ 4 个互动词
        base = "你好" * 300  # 600 字
        script = base + "你看" + base + "说白了" + base + "我觉得" + base + "对吧"
        # 但这样会重复统计，让我们精确构造：
        script = "你看看说白了我觉得对吧" + "你好" * 298  # 4 * 2 + 298 * 2 = 604 字
        # 实际上更简单：直接用 600 字的"你好"加上 4 个分散的互动词
        script = ""
        for i in range(600):
            if i == 100:
                script += "你看"
            elif i == 200:
                script += "说白了"
            elif i == 300:
                script += "我觉得"
            elif i == 400:
                script += "对吧"
            script += "你"
        # 这样: 600 个"你"(600 字) + 4 个互动词(8 字) = 608 字
        # 互动词: "你看""说白了""我觉得""对吧" 各 1 次 = 4 次
        # density = 4 / (608/300) ≈ 1.9737

        stats, _directives = lint_script(script)

        assert stats.char_count > 0
        # 约 2.0（每 300 字互动次数）
        assert 1.5 <= stats.interaction_density <= 2.5


class TestLintTruncation:
    """截断探针测试。"""

    def test_lint_detects_truncated_ending(self) -> None:
        """以省略号收尾但无终止符 → 应检出截断。"""
        script = "这是一篇文章的内容……他接下来说的是"
        stats, directives = lint_script(script)

        assert stats.truncation_suspected is True
        trunc_dirs = [d for d in directives if "截断" in d.problem]
        assert len(trunc_dirs) >= 1
        assert "重新生成而非续写" in trunc_dirs[0].instruction

    def test_lint_clean_ending_not_flagged(self) -> None:
        """以「。」收尾的文本不应被标记截断。"""
        script = "这是一篇完整的文章。"
        stats, _directives = lint_script(script)

        assert stats.truncation_suspected is False

    def test_lint_empty_script_no_crash(self) -> None:
        """空串不抛异常，char_count == 0，且 truncation_suspected == False。"""
        stats, directives = lint_script("")

        assert stats.char_count == 0
        assert stats.truncation_suspected is False

    def test_lint_clean_script_yields_no_directives(self) -> None:
        """干净文本（以「。」收尾）不应产生任何硬伤指令。"""
        script = "今天我们来聊聊英伟达最新的股价表现。内容自然流畅，无特殊标记。"
        _stats, directives = lint_script(script)

        assert len(directives) == 0
