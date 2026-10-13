"""Front-tier parity gates for local runs.

Mirrors anibon-timestamper deterministic steps that need no LLM:
  3.7  analyze_555.py   -> mood_555.json (consumed by state.load_chunk_mood)
  8.5  audit_gaps.py    -> NO GAPS rule
  10   check_sections.py -> byte cap + ASR garble scan
Report-only: gates print findings and never abort the run.
"""
import subprocess
import sys
from pathlib import Path

_PLUGIN_SCRIPTS = Path(__file__).resolve().parents[4] / "scripts"


def _run(script: str, *args) -> int | None:
    path = _PLUGIN_SCRIPTS / script
    if not path.is_file():
        print(f"[gate] skip {script}: not found in {_PLUGIN_SCRIPTS}")
        return None
    r = subprocess.run(
        [sys.executable, "-X", "utf8", str(path), *map(str, args)],
        capture_output=True, text=True,
    )
    out = (r.stdout + r.stderr).strip()
    if out:
        print(f"[gate:{script}]\n{out}")
    return r.returncode


def ensure_mood_555(workspace: Path) -> None:
    """Front-tier Step 3.7: build mood_555.json from aligned livechat if missing."""
    livechat = workspace / "livechat"
    out = workspace / "mood_555.json"
    if out.exists() or not livechat.is_dir():
        return
    args = ["--livechat", livechat, "--out", out]
    index = livechat / "livechat_index.json"
    if index.exists():
        args += ["--index", index]
    _run("analyze_555.py", *args)


def run_parity_gates(workspace: Path, out_md: Path) -> None:
    """Front-tier Steps 8.5 + 10 on the finished run."""
    raw = workspace / "all_timestamps.txt"
    if raw.exists():
        _run("audit_gaps.py", raw, "--chunks-dir", workspace / "chunks")
    if out_md.exists():
        _run("check_sections.py", out_md)
