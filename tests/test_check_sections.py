import subprocess, sys, textwrap
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "skills/anibon-timestamper/scripts/check_sections.py"

VALID_MD = textwrap.dedent("""\
    ══════════════════════════
    📌 ส่วนที่ 1: บทนำการ
    (หัวข้อ: Intro | ⏱ เริ่ม: 00:00:00)
    ══════════════════════════
    00:00:00 - [Greeting] สวัสดี
    00:01:00 - [Talk] คุย
""")

# 1,700 Thai chars × 3 bytes = 5,100 bytes → over the 4,500-byte cap
OVER_LIMIT_MD = VALID_MD + ("00:02:00 - [Talk] " + "ก" * 1700 + "\n")

def _run(md: str, tmp_path: Path) -> int:
    f = tmp_path / "out.md"
    f.write_text(md, encoding="utf-8")
    import os
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(f)],
        capture_output=True,
        env=env,
    )
    return result.returncode

def test_valid_exits_zero(tmp_path):
    assert _run(VALID_MD, tmp_path) == 0

def test_over_limit_exits_nonzero(tmp_path):
    assert _run(OVER_LIMIT_MD, tmp_path) != 0
