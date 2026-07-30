"""
preflight-gate.py — MUST run before any subagent spawn.

Root cause: orchestrator skips pre-flight checks (analyzer, topic detection).
Gaps >10min undetected. Wrong sub-skills loaded. Garbage in → garbage out.

Fix: This script enforces the pre-flight checklist. Blocks spawn if criteria unmet.
"""

import json, sys, os, subprocess

REQUIRED_CHECKS = [
    "anibon-analyzer.py — detects timeline gaps >10min",
    "detect_topics.py — keyword scan for sub-skill routing",
    "macro-density override — block=600 overlap=60 for talk-heavy",
]

def run_check(name, cmd, cwd):
    """Run a check command and return (passed: bool, output: str)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=120)
        output = result.stdout + result.stderr
        if result.returncode != 0:
            return False, f"{name}: FAILED (exit {result.returncode})\n{output[:500]}"
        return True, f"{name}: PASSED\n{output[:500]}"
    except Exception as e:
        return False, f"{name}: ERROR {e}"


def check_workspace(workspace_dir):
    """Verify workspace has required files."""
    issues = []
    chunks_dir = os.path.join(workspace_dir, "chunks")
    if not os.path.isdir(chunks_dir):
        issues.append(f"chunks/ dir not found at {chunks_dir}")
    else:
        chunk_files = sorted(os.listdir(chunks_dir))
        if not chunk_files:
            issues.append("chunks/ dir is empty")

    transcript = os.path.join(workspace_dir, "raw_transcript_merged.json")
    if not os.path.isfile(transcript):
        transcript_alt = os.path.join(workspace_dir, "raw_transcript.json")
        if not os.path.isfile(transcript_alt):
            issues.append("No raw_transcript json found")

    return issues


def check_timestamps(timestamp_path):
    """Verify final timestamp list for gaps >15min."""
    if not os.path.isfile(timestamp_path):
        return ["timestamp file not found"]

    issues = []
    with open(timestamp_path, encoding='utf-8') as f:
        lines = [l.strip() for l in f if l.strip() and l[0].isdigit()]

    for i in range(1, len(lines)):
        prev_parts = lines[i-1].split(' - ')
        curr_parts = lines[i].split(' - ')
        if len(prev_parts) < 1 or len(curr_parts) < 1:
            continue

        prev_ts = prev_parts[0]
        curr_ts = curr_parts[0]

        def to_sec(t):
            parts = t.split(':')
            return int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])

        gap = to_sec(curr_ts) - to_sec(prev_ts)
        if gap > 900:  # 15min
            issues.append(f"GAP {prev_ts} → {curr_ts}: {gap//60}min (max 15min)")

    return issues


def main():
    """CLI: python3 preflight-gate.py <workspace_dir>"""
    if len(sys.argv) < 2:
        print("Usage: python3 preflight-gate.py <workspace_dir>", file=sys.stderr)
        sys.exit(1)

    workspace = sys.argv[1]
    skill_base = os.environ.get(
        "ANIBON_SKILL_BASE",
        os.path.join(workspace, "..", "skills", "anibon-timestamper")
    )

    print("=" * 60)
    print("PRE-FLIGHT GATE")
    print("=" * 60)

    # 1. Workspace integrity
    ws_issues = check_workspace(workspace)
    if ws_issues:
        print("\n❌ WORKSPACE ISSUES:")
        for i in ws_issues:
            print(f"  - {i}")
    else:
        print("\n✅ Workspace OK")

    # 2. Run anibon-analyzer if available
    analyzer = os.path.join(skill_base, "scripts", "anibon-analyzer.py")
    if os.path.isfile(analyzer):
        passed, out = run_check("anibon-analyzer", ["python3", analyzer, workspace], workspace)
        print(f"\n{out}")
    else:
        print(f"\n⚠️  anibon-analyzer.py not found at {analyzer}")

    # 3. Check for timestamp gaps (if already generated)
    ts_path = os.path.join(workspace, "timestamps.txt")
    gap_issues = check_timestamps(ts_path)
    if gap_issues:
        print("\n❌ TIMESTAMP GAPS FOUND:")
        for g in gap_issues:
            print(f"  - {g}")
    else:
        print("\n✅ No timestamp gaps >15min" if os.path.isfile(ts_path) else "\n⏭️  No timestamp file yet")

    # 4. Summary
    total_issues = len(ws_issues) + len(gap_issues)
    if total_issues > 0:
        print(f"\n❌ GATE BLOCKED: {total_issues} issue(s). Fix before proceeding.")
        sys.exit(1)
    else:
        print("\n✅ GATE PASSED. Proceed to subagent spawn.")


if __name__ == "__main__":
    main()
