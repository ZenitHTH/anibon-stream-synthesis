#!/usr/bin/env python3
"""CLI helper for anibon_wiki: stats, search, lint, and raw source snapshots."""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

WIKI_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = WIKI_ROOT.parent
WIKI_DIR = WIKI_ROOT / "wiki"
RAW_DIR = WIKI_ROOT / "raw"
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]+)?\]\]")


def _all_wiki_pages() -> dict[str, Path]:
    pages: dict[str, Path] = {}
    for p in sorted(WIKI_DIR.rglob("*.md")):
        if "_templates" in p.parts:
            continue
        pages[p.stem] = p
    return pages


def cmd_stats(_args: argparse.Namespace) -> int:
    pages = _all_wiki_pages()
    raw_files = [p for p in RAW_DIR.rglob("*") if p.is_file()]
    words = sum(len(p.read_text(encoding="utf-8", errors="replace").split()) for p in pages.values())
    print(f"Wiki root:  {WIKI_ROOT}")
    print(f"Raw files:  {len(raw_files)}")
    print(f"Wiki pages: {len(pages)} ({words:,} words)")
    by_folder: dict[str, int] = {}
    for p in pages.values():
        rel = str(p.parent.relative_to(WIKI_DIR))
        by_folder[rel] = by_folder.get(rel, 0) + 1
    for folder, count in sorted(by_folder.items()):
        print(f"  - wiki/{folder}: {count}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    q = args.query.lower()
    hits = 0
    for stem, p in _all_wiki_pages().items():
        for lineno, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if q in line.lower():
                rel = p.relative_to(WIKI_ROOT)
                print(f"{rel}:{lineno}: {line.strip()}")
                hits += 1
    print(f"--- {hits} match(es) for '{args.query}' ---")
    return 0


def cmd_lint(_args: argparse.Namespace) -> int:
    pages = _all_wiki_pages()
    broken: list[tuple[Path, str]] = []
    inbound: dict[str, int] = {stem: 0 for stem in pages}
    for stem, p in pages.items():
        text = p.read_text(encoding="utf-8", errors="replace")
        for target in _WIKILINK_RE.findall(text):
            slug = Path(target.strip()).stem
            if not slug:
                continue
            if slug not in pages:
                broken.append((p.relative_to(WIKI_ROOT), slug))
            elif slug != stem:
                inbound[slug] = inbound.get(slug, 0) + 1
    core = {"index", "overview", "log"}
    orphans = [s for s, c in inbound.items() if c == 0 and s not in core]
    idx_text = (WIKI_DIR / "index.md").read_text(encoding="utf-8", errors="replace") if (WIKI_DIR / "index.md").is_file() else ""
    unindexed = [s for s in pages if s not in core and f"[[{s}" not in idx_text]
    print(f"Checked {len(pages)} wiki pages.")
    print(f"  Broken wikilinks: {len(broken)}")
    for src, slug in broken:
        print(f"    - {src} -> [[{slug}]]")
    print(f"  Orphan pages:     {len(orphans)} {orphans if orphans else ''}")
    print(f"  Unindexed pages:  {len(unindexed)} {unindexed if unindexed else ''}")
    return 1 if (broken or orphans or unindexed) else 0


def cmd_acquire_stream(args: argparse.Namespace) -> int:
    ws = Path(args.workspace).expanduser().resolve()
    vid = args.video_id or ws.name.replace("youtube_", "").replace("_workspace", "")
    ts_md = ws / "anibon_timestamps.md"
    all_txt = ws / "all_timestamps.txt"
    if not ts_md.is_file():
        print(f"Missing {ts_md}", file=sys.stderr)
        return 1
    dest = RAW_DIR / "streams" / f"stream-{vid.lower()}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    body = [
        f"# Raw Stream Snapshot: {vid}",
        f"- Acquired: {date.today().isoformat()}",
        f"- Workspace: `{ws}`",
        f"- YouTube: `https://www.youtube.com/watch?v={vid}`",
        "",
        "## Curated Essential Timestamps (`anibon_timestamps.md`)",
        ts_md.read_text(encoding="utf-8", errors="replace").strip(),
    ]
    if all_txt.is_file():
        body.extend([
            "",
            "## Exhaustive Chronological Timestamps (`all_timestamps.txt`)",
            all_txt.read_text(encoding="utf-8", errors="replace").strip(),
        ])
    dest.write_text("\n".join(body) + "\n", encoding="utf-8")
    print(f"Acquired stream -> {dest}")
    return 0


def cmd_acquire_git(args: argparse.Namespace) -> int:
    rev_range = args.rev_range
    slug = args.slug
    log_out = subprocess.check_output(
        ["git", "log", "--stat", "-p", rev_range],
        cwd=str(REPO_ROOT),
        text=True,
        errors="replace",
    )
    dest = RAW_DIR / "code-changes" / f"{slug}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    plan_txt = ""
    if args.plan and Path(args.plan).is_file():
        plan_txt = "\n## Implementation Plan\n" + Path(args.plan).read_text(encoding="utf-8", errors="replace")
    dest.write_text(
        f"# Raw Code Change Snapshot: {slug}\n- Revision Range: `{rev_range}`\n- Acquired: {date.today().isoformat()}\n{plan_txt}\n\n## Git Log & Diff\n```diff\n{log_out[:60000]}\n```\n",
        encoding="utf-8",
    )
    print(f"Acquired git range {rev_range} -> {dest}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Anibon LLM Wiki CLI Tool")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stats")
    p_s = sub.add_parser("search")
    p_s.add_argument("query")
    sub.add_parser("lint")
    p_st = sub.add_parser("acquire-stream")
    p_st.add_argument("workspace")
    p_st.add_argument("--video-id", default="")
    p_gt = sub.add_parser("acquire-git")
    p_gt.add_argument("rev_range")
    p_gt.add_argument("slug")
    p_gt.add_argument("--plan", default="")
    args = ap.parse_args()
    dispatch = {
        "stats": cmd_stats,
        "search": cmd_search,
        "lint": cmd_lint,
        "acquire-stream": cmd_acquire_stream,
        "acquire-git": cmd_acquire_git,
    }
    return dispatch[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
