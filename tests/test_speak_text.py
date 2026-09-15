"""Tests for TTS speak_text sanitization."""

from runtime.transport.speech.speak_text import (
    SentenceBuffer,
    is_speakable,
    speak_text,
    take_sentences,
)


def test_strips_markdown_emoji_bullets() -> None:
    raw = (
        "你好！我是运行在 **pi** 编码代理程序中的 AI 编程助手。\n\n"
        "我可以帮你：\n"
        "- 📖 阅读和分析代码文件\n"
        "- ✏️ 编写和修改代码\n"
        "- 🔧 解决编程问题\n"
        "- 🚀 搭建项目结构\n\n"
        "有什么我可以帮你的吗？"
    )
    out = speak_text(raw)
    assert "**" not in out
    assert "📖" not in out
    assert "pi" in out.lower()
    assert "AI" in out
    assert "阅读和分析代码文件" in out
    assert "有什么我可以帮你的吗" in out


def test_keeps_latin_and_parens_for_multilingual() -> None:
    raw = "我是运行在 pi（一个编码智能体框架）中的编程助手。需要我做什么？"
    out = speak_text(raw)
    assert "pi" in out.lower()
    assert "编程助手" in out
    assert "编码智能体框架" in out
    assert "需要我做什么" in out


def test_keeps_english_sentence() -> None:
    out = speak_text("Sure, I can help you with Markdown.")
    assert "Sure" in out
    assert "Markdown" in out
    assert "**" not in out


def test_strips_cjk_quotes() -> None:
    out = speak_text("请把「做出来」写进文档。")
    assert "「" not in out and "」" not in out
    assert "做出来" in out
    out2 = speak_text("他说『你好』和“世界”。")
    assert "『" not in out2 and "』" not in out2
    assert "“" not in out2 and "”" not in out2
    assert "你好" in out2 and "世界" in out2


def test_empty() -> None:
    assert speak_text("") == ""
    assert speak_text("   ") == ""


def test_is_speakable_rejects_punctuation_only() -> None:
    assert not is_speakable("。")
    assert not is_speakable("！？")
    assert not is_speakable("...")
    assert is_speakable("好。")
    assert is_speakable("OK")
    assert is_speakable("A")


def test_take_sentences_skips_bare_period() -> None:
    sents, rest = take_sentences("你好。。还有")
    assert sents == ["你好。"]
    assert rest == "还有"

    sents, rest = take_sentences("你好。世界！还有")
    assert sents == ["你好。", "世界！"]
    assert rest == "还有"


def test_take_sentences_force_flush() -> None:
    sents, rest = take_sentences("尾巴没有句号", force=True)
    assert sents == ["尾巴没有句号"]
    assert rest == ""


def test_take_sentences_soft_split() -> None:
    long = "这是一段很长的话，中间有逗号可以切开，" + ("啊" * 40)
    sents, rest = take_sentences(long, force_at=20)
    assert sents
    assert all(sents)
    assert len(sents[0]) <= len(long)


def test_sentence_buffer_streaming() -> None:
    buf = SentenceBuffer(force_at=80)
    assert buf.push("你好") == []
    assert buf.push("世界。下一句") == ["你好世界。"]
    assert buf.flush() == ["下一句"]
