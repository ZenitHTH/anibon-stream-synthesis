import sys
from pathlib import Path
import json
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from assemble_timestamps import format_sections, load_parts


SAMPLE_PARTS = [
    {
        "title": "Opening",
        "start": "00:00:00",
        "desc": "Intro segment",
        "body": "00:00:00 - [Greeting] Hello viewers"
    },
    {
        "title": "Main Topic",
        "start": "00:10:00",
        "desc": "Discussion segment",
        "body": "00:10:00 - [Talk] Main discussion"
    },
]


def test_format_sections_contains_all_parts():
    result = format_sections(SAMPLE_PARTS)
    assert "📌 ส่วนที่ 1" in result
    assert "📌 ส่วนที่ 2" in result
    assert "Intro segment" in result
    assert "Discussion segment" in result
    assert "00:00:00 - [Greeting] Hello viewers" in result


def test_format_sections_header_format():
    result = format_sections(SAMPLE_PARTS)
    assert "หัวข้อ: Opening" in result
    assert "⏱ เริ่ม: 00:00:00" in result


def test_load_parts_valid(tmp_path):
    json_file = tmp_path / "parts.json"
    json_file.write_text(json.dumps(SAMPLE_PARTS), encoding="utf-8")
    parts = load_parts(json_file)
    assert len(parts) == 2
    assert parts[0]["title"] == "Opening"


def test_load_parts_missing_key(tmp_path):
    bad = [{"title": "Bad", "start": "00:00:00"}]  # missing desc and body
    json_file = tmp_path / "bad.json"
    json_file.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(SystemExit):
        load_parts(json_file)
