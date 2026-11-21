#!/usr/bin/env python3
"""Batch-ingest all raw/streams/*.md snapshots into wiki/sources/ and build category packs."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

from stream_taxonomy import classify_stream, sanitize_wiki_text

WIKI_ROOT = Path(__file__).resolve().parents[1]
RAW_STREAMS = WIKI_ROOT / "raw" / "streams"
WIKI_SOURCES = WIKI_ROOT / "wiki" / "sources"
_SECTION_RE = re.compile(r"^\s*ส่วนที่\s*(\d+)\s*[:：]\s*(.+)$")
_STAMP_RE = re.compile(r"^(?:-?\s*\*\*)?(\d{2}:\d{2}:\d{2})(?:\*\*)?\s*-\s*(.+)$")


def _extract_meta(curated: str, slug: str) -> dict:
    """Extract video_id, title, upload_date, primary_source from raw snapshot header."""
    def grab(pattern: str, default: str = "") -> str:
        m = re.search(pattern, curated, re.M)
        return m.group(1).strip() if m else default

    vid = grab(r"^#\s+Raw Stream Snapshot:\s*(.+)$", slug.replace("stream-", ""))
    title = sanitize_wiki_text(grab(r"^- Title:\s*(.+)$", f"ANIBON Stream {vid}"))
    title = title.replace('"', "'")
    dt = grab(r"^- Upload Date:\s*(.+)$", "unknown")
    primary = grab(r"^- Primary Source:\s*`(.+)`$", "")
    return {"slug": slug, "vid": vid, "title": title, "date": dt, "primary": primary}


def _parse_sections_and_stamps(curated: str) -> Tuple[List[str], List[str]]:
    """Extract clean section headers and HH:MM:SS timestamp bullets."""
    sections: List[str] = []
    stamps: List[str] = []
    for raw_ln in curated.splitlines():
        ln = raw_ln.strip()
        if not ln or ln.startswith(("══", "---")):
            continue
        sm = _SECTION_RE.match(ln)
        if sm:
            clean_sec = sanitize_wiki_text(sm.group(2).strip())
            sections.append(f"ส่วนที่ {sm.group(1)}: {clean_sec}")
            continue
        tm = _STAMP_RE.match(ln)
        if tm:
            desc = sanitize_wiki_text(tm.group(2).strip())
            stamps.append(f"- `{tm.group(1)}` — {desc}")
    return sections, stamps


def _render_source_page(meta: dict, cats: Dict[str, List[str]], sections: List[str], stamps: List[str], raw_path: Path) -> str:
    """Render structured markdown page for wiki/sources/<slug>.md."""
    all_tags = sorted(set(["stream", "anibon"] + cats["games"] + cats["topics"]))
    primary_link = f"[Original Timestamps](file://{meta['primary']})" if meta["primary"] else ""
    raw_link = f"[Raw Snapshot](file://{raw_path.resolve()})"
    lines = [
        "---",
        f'title: "Stream {meta["vid"]} — {meta["title"]}"',
        'category: "source"',
        'updated: "2026-11-21"',
        f'video_id: "{meta["vid"]}"',
        f'upload_date: "{meta["date"]}"',
        f"tags: {json.dumps(all_tags, ensure_ascii=False)}",
        "sources: []",
        'status: "active"',
        "---",
        "",
        f"# Stream `{meta['vid']}` — {meta['title']}",
        "",
        f"- **Upload Date**: `{meta['date']}`",
        f"- **YouTube URL**: `https://www.youtube.com/watch?v={meta['vid']}`",
        f"- **Files**: {raw_link}" + (f" · {primary_link}" if primary_link else ""),
        "",
        "## Linked Categories & Entities",
        f"- **Games**: {', '.join(f'[[{g}]]' for g in cats['games']) or '—'}",
        f"- **Entities**: {', '.join(f'[[{e}]]' for e in cats['entities']) or '—'}",
        f"- **Topics**: {', '.join(f'[[{t}]]' for t in cats['topics']) or '—'}",
    ]
    if sections:
        lines.extend(["", "## Macro-Thematic Sections"])
        lines.extend(f"- {s}" for s in sections)
    if stamps:
        lines.extend(["", f"## Curated Timeline ({len(stamps)} timestamps)"])
        lines.extend(stamps)
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Batch-ingest raw/streams/*.md into wiki/sources/")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing generated source pages (except stream-cqll7dq35bw)")
    ap.add_argument("--packs-dir", default="/tmp/anibon_category_packs")
    args = ap.parse_args()

    WIKI_SOURCES.mkdir(parents=True, exist_ok=True)
    packs_dir = Path(args.packs_dir)
    packs_dir.mkdir(parents=True, exist_ok=True)
    category_buckets: Dict[str, List[dict]] = {}
    written = 0
    manifest_rows: List[dict] = []

    for raw_path in sorted(RAW_STREAMS.glob("stream-*.md")):
        slug = raw_path.stem
        txt = raw_path.read_text(encoding="utf-8", errors="replace")
        curated = txt.split("## Exhaustive Chronological Timestamps")[0]
        meta = _extract_meta(curated, slug)
        cats = classify_stream(sanitize_wiki_text(curated).lower())
        sections, stamps = _parse_sections_and_stamps(curated)

        out_path = WIKI_SOURCES / f"{slug}.md"
        if slug != "stream-cqll7dq35bw" and (args.overwrite or not out_path.is_file()):
            out_path.write_text(_render_source_page(meta, cats, sections, stamps, raw_path), encoding="utf-8")
            written += 1

        row = {
            "slug": slug,
            "vid": meta["vid"],
            "date": meta["date"],
            "title": meta["title"],
            "sections": sections,
            "stamps_preview": stamps[:25],
            "games": cats["games"],
            "entities": cats["entities"],
            "topics": cats["topics"],
        }
        manifest_rows.append(row)
        for cat in cats["games"] + cats["entities"] + cats["topics"]:
            category_buckets.setdefault(cat, []).append(row)

    for cat, rows in sorted(category_buckets.items()):
        rows_sorted = sorted(rows, key=lambda r: r["date"], reverse=True)
        out_pack = packs_dir / f"{cat}.json"
        out_pack.write_text(json.dumps(rows_sorted, ensure_ascii=False, indent=2), encoding="utf-8")

    (packs_dir / "_all_streams.json").write_text(
        json.dumps(sorted(manifest_rows, key=lambda r: r["date"], reverse=True), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Processed {len(manifest_rows)} raw streams | newly written source pages: {written} | category packs: {len(category_buckets)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
