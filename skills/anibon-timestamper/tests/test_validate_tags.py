"""Tests for validate_tags.py — keyword-based tag validation + retag."""
import sys
import pathlib
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scripts"))
from validate_tags import (
    parse_line,
    suggest_retag,
    check_false_positive,
    validate_file,
)


# ─────────────────────────────────────────────────────────────
# parse_line
# ─────────────────────────────────────────────────────────────

def test_parse_standard():
    result = parse_line("00:15:30 - [Gameplay] Fighting god boss")
    assert result is not None
    assert result[0] == "00:15:30"
    assert result[1] == "[Gameplay]"
    assert result[2] == "Fighting god boss"


def test_parse_no_match():
    assert parse_line("garbage line without timestamp") is None


def test_parse_empty():
    assert parse_line("") is None


# ─────────────────────────────────────────────────────────────
# suggest_retag — boss keywords
# ─────────────────────────────────────────────────────────────

def test_boss_retag():
    tag, reason = suggest_retag("สู้บอสตัวนี้ยากมาก", "[Gameplay]")
    assert tag == "[Boss]", f"Expected [Boss], got {tag}"
    assert reason is not None


def test_boss_already_correct():
    result = suggest_retag("สู้บอสตัวนี้ยากมาก", "[Boss]")
    assert result[0] is None  # None = no change


def test_boss_english():
    tag, _ = suggest_retag("boss fight at final stage", "[Gameplay]")
    assert tag == "[Boss]"


# ─────────────────────────────────────────────────────────────
# Death keywords
# ─────────────────────────────────────────────────────────────

def test_death_retag():
    tag, _ = suggest_retag("ตายแล้วไอ้นี่", "[Gameplay]")
    assert tag == "[Death]"


def test_death_already_correct():
    result = suggest_retag("ตายหมดทั้งทีม", "[Death]")
    assert result[0] is None


# ─────────────────────────────────────────────────────────────
# Victory keywords
# ─────────────────────────────────────────────────────────────

def test_victory_retag():
    tag, _ = suggest_retag("เคลียร์บอสแล้ว", "[Gameplay]")
    assert tag == "[Victory]"


def test_victory_english():
    tag, _ = suggest_retag("clear mission complete", "[Gameplay]")
    assert tag == "[Victory]"


def test_victory_already_correct():
    result = suggest_retag("เคลียร์บอสแล้ว", "[Victory]")
    assert result[0] is None


# ─────────────────────────────────────────────────────────────
# Other tag retags
# ─────────────────────────────────────────────────────────────

def test_gacha_retag():
    tag, _ = suggest_retag("จิ้มกาชา 10 โรล", "[Gameplay]")
    assert tag == "[Gacha]"


def test_chat_retag():
    tag, _ = suggest_retag("ในแชทบอกว่าให้ลองใหม่", "[Talk]")
    assert tag == "[Chat]"


def test_reaction_retag():
    tag, _ = suggest_retag("ดูคลิปอนิเมะตัวอย่าง", "[Talk]")
    assert tag == "[Reaction]"


def test_news_retag():
    tag, _ = suggest_retag("มีข่าวอัปเดตเกมใหม่", "[Gameplay]")
    assert tag == "[News]"


def test_donation_retag():
    tag, _ = suggest_retag("ขอบคุณครับสำหรับ super chat", "[Talk]")
    assert tag == "[Donation]"


# ─────────────────────────────────────────────────────────────
# No-match — keep original
# ─────────────────────────────────────────────────────────────

def test_no_keyword_match():
    result = suggest_retag("เดินเล่นในเมืองเฉยๆ", "[Gameplay]")
    assert result[0] is None


def test_generic_talk():
    result = suggest_retag("วันนี้อากาศดี", "[Talk]")
    assert result[0] is None


# ─────────────────────────────────────────────────────────────
# False positive blocking
# ─────────────────────────────────────────────────────────────

def test_boss_false_positive():
    """'บอส' in 'บอสว่า' (Boat says 'boss said') should NOT trigger retag."""
    result = suggest_retag("บอสว่ายังไงบ้าง", "[Gameplay]")
    assert result[0] is None, f"Should be blocked: {result}"


def test_boss_false_positive_chat():
    result = suggest_retag("พูดถึงบอสเก่า", "[Talk]")
    assert result[0] is None


# ─────────────────────────────────────────────────────────────
# check_false_positive helper
# ─────────────────────────────────────────────────────────────

def test_false_positive_blocks():
    assert check_false_positive("บอสว่ายังไง", "[Boss]") is True
    assert check_false_positive("สู้บอส", "[Boss]") is False
    assert check_false_positive("พูดถึงบอส", "[Boss]") is True
    assert check_false_positive("เกียวตาย", "[Death]") is True
    assert check_false_positive("ตายแล้ว", "[Death]") is False


# ─────────────────────────────────────────────────────────────
# Integration: validate_file
# ─────────────────────────────────────────────────────────────

def test_validate_file_retags():
    input_lines = [
        "00:15:30 - [Gameplay] สู้บอสตัวนี้ยากมาก\n",
        "00:20:00 - [Gameplay] เดินเล่นในเมือง\n",
        "00:25:00 - [Gameplay] ตายหมดทั้งทีม\n",
        "01:00:00 - [Boss] สู้บอสอีกตัว\n",  # already correct
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f_in:
        f_in.writelines(input_lines)
        in_path = pathlib.Path(f_in.name)

    out_path = in_path.parent / f"{in_path.stem}_validated.txt"

    try:
        stats = validate_file(in_path, out_path)
        assert stats["total"] == 4
        assert stats["changed"] == 2  # lines 1 and 3
        assert stats["unchanged"] == 2  # lines 2 and 4
        assert stats["skipped"] == 0

        # Verify output content
        out_lines = out_path.read_text(encoding="utf-8").strip().split("\n")
        assert "[Boss]" in out_lines[0], f"Expected [Boss] retag: {out_lines[0]}"
        assert "[Gameplay]" in out_lines[1], f"Unchanged: {out_lines[1]}"
        assert "[Death]" in out_lines[2], f"Expected [Death] retag: {out_lines[2]}"
        assert "[Boss]" in out_lines[3], f"Already correct: {out_lines[3]}"
    finally:
        in_path.unlink(missing_ok=True)
        out_path.unlink(missing_ok=True)


def test_validate_file_empty():
    """Empty input → empty output."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f_in:
        in_path = pathlib.Path(f_in.name)

    out_path = in_path.parent / f"{in_path.stem}_validated.txt"

    try:
        stats = validate_file(in_path, out_path)
        assert stats["total"] == 0
        assert stats["changed"] == 0
        out_content = out_path.read_text(encoding="utf-8").strip()
        assert out_content == ""
    finally:
        in_path.unlink(missing_ok=True)
        out_path.unlink(missing_ok=True)
