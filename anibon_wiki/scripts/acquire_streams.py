#!/usr/bin/env python3
"""Bulk acquire all ANIBON livestream timestamps from HOME directories into raw/streams/."""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

WIKI_ROOT = Path(__file__).resolve().parents[1]
RAW_STREAMS = WIKI_ROOT / "raw" / "streams"
EXCLUDED_IDS = {"DiI0GEBVIxQ", "lUpikjLTmro"}
_README_ROW_RE = re.compile(
    r"^\|\s*(\d{2}/\d{2}/\d{4})\s*\|\s*([A-Za-z0-9_-]{6,})\s*\|\s*\[(.+?)\]\("
)


def _normalize_date(raw_date: str) -> str:
    """Convert DD/MM/YYYY or YYYYMMDD to YYYY-MM-DD."""
    s = (raw_date or "").strip()
    if re.match(r"^\d{2}/\d{2}/\d{4}$", s):
        dd, mm, yyyy = s.split("/")
        return f"{yyyy}-{mm}-{dd}"
    if re.match(r"^\d{8}$", s):
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s


def _load_readme_meta(ts_ws: Path) -> Dict[str, Tuple[str, str]]:
    """Parse (date, title) metadata map from timestamp_workspace/README.md."""
    readme = ts_ws / "README.md"
    if not readme.is_file():
        return {}
    meta: Dict[str, Tuple[str, str]] = {}
    for line in readme.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _README_ROW_RE.match(line.strip())
        if m:
            dt = _normalize_date(m.group(1))
            vid = m.group(2).strip()
            title = m.group(3).replace("\\|", "|").strip()
            meta[vid] = (dt, title)
    return meta


def _read_info_meta(ws_dir: Path) -> Tuple[str, str]:
    """Read (date, title) from workspace info.json if present."""
    for name in ("info.json", "info.info.json"):
        p = ws_dir / name
        if p.is_file():
            try:
                d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
                return _normalize_date(str(d.get("upload_date") or "")), str(d.get("title") or "").strip()
            except Exception:
                pass
    return "", ""


def _canonical_vid(raw_vid: str) -> Optional[str]:
    """Extract canonical 11-char YouTube video ID, skipping unmasked variants."""
    if "_unmasked" in raw_vid.lower():
        return None
    m = re.match(r"^([A-Za-z0-9_-]{11})(?:_[A-Za-z0-9_-]+)?$", raw_vid)
    return m.group(1) if m else raw_vid


def _pick_best_source(home: Path) -> Dict[str, dict]:
    """Collect best timestamp source file per canonical 11-char ANIBON video_id."""
    readme_meta = _load_readme_meta(home / "timestamp_workspace")
    chosen: Dict[str, dict] = {}

    def register(raw_vid: str, prio: int, primary: Path, all_ts: Optional[Path] = None, info_dir: Optional[Path] = None) -> None:
        vid = _canonical_vid(raw_vid)
        if not vid or vid in EXCLUDED_IDS or not primary.is_file():
            return
        cur = chosen.get(vid)
        if cur and cur["prio"] <= prio:
            return
        dt, title = readme_meta.get(vid, ("", ""))
        if info_dir and (not dt or not title):
            i_dt, i_title = _read_info_meta(info_dir)
            dt = dt or i_dt
            title = title or i_title
        if not title:
            first = primary.read_text(encoding="utf-8", errors="replace").splitlines()[:5]
            for ln in first:
                if ln.startswith("# "):
                    title = ln[2:].strip()
                    break
        chosen[vid] = {
            "vid": vid,
            "prio": prio,
            "primary": primary,
            "all_ts": all_ts if (all_ts and all_ts.is_file()) else None,
            "date": dt,
            "title": title or f"ANIBON Stream {vid}",
        }

    for d in sorted(home.glob("youtube_*_workspace*")):
        m = re.match(r"youtube_(.+?)_workspace", d.name) if d.is_dir() else None
        if not m:
            continue
        vid = m.group(1)
        for p_idx, fn in enumerate(("anibon_timestamps.md", "output.md"), start=1):
            if (d / fn).is_file():
                register(vid, p_idx, d / fn, d / "all_timestamps.txt", d)
                break

    for p in sorted((home / "timestamp_workspace" / "by_video_id").glob("timestamp_*.md")):
        raw_vid = p.stem[len("timestamp_"):]
        is_exact = len(raw_vid) == 11
        register(raw_vid, 3 if is_exact else 4, p, None, None)

    backed = home / "youtube_workspaces" / "backed_up"
    if backed.is_dir():
        for d in sorted(backed.iterdir()):
            m = re.match(r"youtube_(.+?)_workspace", d.name) if d.is_dir() else None
            if not m:
                continue
            vid = m.group(1)
            for p_idx, fn in enumerate(("anibon_timestamps_essential.md", "anibon_timestamps.md", "output.md"), start=5):
                if (d / fn).is_file():
                    register(vid, p_idx, d / fn, d / "all_timestamps.txt", d)
                    break

    return chosen


def write_raw_snapshot(entry: dict, force: bool = False) -> Tuple[Path, bool]:
    """Write immutable raw snapshot markdown for one stream."""
    vid = entry["vid"]
    dest = RAW_STREAMS / f"stream-{vid.lower()}.md"
    if dest.is_file() and not force:
        return dest, False
    RAW_STREAMS.mkdir(parents=True, exist_ok=True)
    primary_txt = entry["primary"].read_text(encoding="utf-8", errors="replace").strip()
    lines = [
        f"# Raw Stream Snapshot: {vid}",
        f"- Title: {entry['title']}",
        f"- Upload Date: {entry['date'] or 'unknown'}",
        f"- Acquired: {date.today().isoformat()}",
        f"- Primary Source: `{entry['primary']}`",
        f"- YouTube: `https://www.youtube.com/watch?v={vid}`",
        "",
        "## Curated Timestamps",
        primary_txt,
    ]
    if entry["all_ts"]:
        lines.extend([
            "",
            "## Exhaustive Chronological Timestamps (`all_timestamps.txt`)",
            entry["all_ts"].read_text(encoding="utf-8", errors="replace").strip(),
        ])
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest, True


def main() -> int:
    ap = argparse.ArgumentParser(description="Bulk acquire all ANIBON streams into raw/streams/")
    ap.add_argument("--home", default=str(Path.home()))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    entries = _pick_best_source(Path(args.home))
    created = 0
    for vid in sorted(entries):
        _, wrote = write_raw_snapshot(entries[vid], force=args.force)
        created += int(wrote)
    print(f"Total unique ANIBON streams: {len(entries)} | newly written/updated: {created}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
