"""Structured multi-term search engine over anibon_wiki pages and optional raw snapshots."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from stream_taxonomy import sanitize_wiki_text
except ImportError:
    from anibon_wiki.scripts.stream_taxonomy import sanitize_wiki_text  # type: ignore

_HMS_RE = re.compile(r"(?:`(\d{2}:\d{2}:\d{2})`|\b(\d{2}:\d{2}:\d{2})\b)")
_SYNTH_DIRS = frozenset({"games", "entities", "topics"})
_SKIP_STEMS = frozenset({"index", "log"})
_TIER_BOOST = {"synthesis": 50, "stream": 20, "engineering": 10, "raw": 5}


@dataclass(frozen=True)
class SearchSpec:
    """Query parameters for searching anibon_wiki."""

    terms: Tuple[str, ...]
    tags: Tuple[str, ...] = ()
    category: str = ""
    date_from: str = ""
    date_to: str = ""
    limit: int = 20
    include_raw: bool = False


def hms_to_seconds(hms: str) -> int:
    """Convert HH:MM:SS string to integer seconds."""
    hh, mm, ss = (int(part) for part in hms.split(":"))
    return hh * 3600 + mm * 60 + ss


def _build_youtube_url(vid: str, secs: Optional[int]) -> str:
    if not vid:
        return ""
    base = f"https://www.youtube.com/watch?v={vid}"
    return f"{base}&t={secs}" if secs is not None else base


def _grab_scalar(header: str, key: str) -> str:
    m = re.search(rf'^{key}:\s*"?([^"\n]+?)"?\s*$', header, re.M)
    return m.group(1).strip() if m else ""


def _parse_frontmatter(text: str, path: Path) -> Dict[str, Any]:
    """Parse YAML frontmatter metadata and the 0-based body start line index."""
    meta: Dict[str, Any] = {"title": path.stem, "category": "", "video_id": "", "upload_date": "", "tags": [], "body_idx": 0}
    if not text.startswith("---\n"):
        return meta
    end = text.find("\n---\n", 4)
    if end == -1:
        return meta
    header = text[4:end]
    meta["body_idx"] = text[: end + 5].count("\n")
    for field in ("title", "category", "video_id", "upload_date"):
        if val := _grab_scalar(header, field):
            meta[field] = val
    if tm := re.search(r"^tags:\s*(\[[^\n]+\])", header, re.M):
        try:
            meta["tags"] = [str(t).lower() for t in json.loads(tm.group(1))]
        except json.JSONDecodeError:
            meta["tags"] = []
    return meta


def _page_tier(wiki_root: Path, path: Path) -> str:
    rel = path.relative_to(wiki_root)
    if rel.parts[0] == "raw":
        return "raw"
    if len(rel.parts) >= 2 and rel.parts[1] in _SYNTH_DIRS or path.stem == "overview":
        return "synthesis"
    return "stream" if (len(rel.parts) >= 2 and rel.parts[1] == "sources") else "engineering"


def _iter_candidate_files(wiki_root: Path, spec: SearchSpec) -> List[Tuple[str, Path]]:
    items = [
        (_page_tier(wiki_root, p), p)
        for p in sorted((wiki_root / "wiki").rglob("*.md"))
        if "_templates" not in p.parts and p.stem not in _SKIP_STEMS
    ]
    if spec.include_raw:
        items.extend(("raw", p) for p in sorted((wiki_root / "raw" / "streams").glob("*.md")))
    return items


def _matches_filters(meta: Dict[str, Any], tier: str, spec: SearchSpec) -> bool:
    if spec.category and spec.category.lower() not in {meta["category"].lower(), tier}:
        return False
    if spec.tags and not all(t.lower() in meta["tags"] for t in spec.tags):
        return False
    dt = meta["upload_date"]
    if spec.date_from and (not dt or dt == "unknown" or dt < spec.date_from):
        return False
    return not (spec.date_to and (not dt or dt == "unknown" or dt > spec.date_to))


def _collect_line_matches(lines: List[str], spec_ctx: Tuple[Tuple[str, ...], str, int]) -> List[Dict[str, Any]]:
    """Collect sanitized body matches; prioritize lines carrying HH:MM:SS timestamps."""
    low_terms, vid, body_idx = spec_ctx
    timed, plain = [], []
    section = ""
    for lineno, raw in enumerate(lines[body_idx:], body_idx + 1):
        stripped = raw.strip()
        if stripped.startswith(("## ", "### ")):
            section = stripped.lstrip("# ").strip()
        if not any(term in stripped.lower() for term in low_terms):
            continue
        hm = _HMS_RE.search(stripped)
        hms = (hm.group(1) or hm.group(2)) if hm else ""
        secs = hms_to_seconds(hms) if hms else None
        hit = {"line": lineno, "section": section, "timestamp": hms, "seconds": secs, "youtube_url": _build_youtube_url(vid, secs), "text": sanitize_wiki_text(stripped)}
        (timed if secs is not None else plain).append(hit)
    return (timed + plain)[:12]


def _score_doc(meta: Dict[str, Any], low_terms: Tuple[str, ...], text_low: str) -> int:
    matched = sum(1 for t in low_terms if t in text_low)
    if matched == 0:
        return 0
    tags_blob = " ".join(meta["tags"])
    bonus = sum(15 for t in low_terms if t in meta["title"].lower() or t in tags_blob)
    return bonus + matched * 10


def _wiki_coverage(wiki_dir: Path) -> Dict[str, Any]:
    pages = [p for p in wiki_dir.rglob("*.md") if "_templates" not in p.parts]
    streams = list((wiki_dir / "sources").glob("stream-*.md"))
    dates = [dt for p in streams if re.match(r"^\d{4}-\d{2}-\d{2}$", dt := _grab_scalar(p.read_text(encoding="utf-8", errors="replace")[:500], "upload_date"))]
    return {"total_pages": len(pages), "total_streams": len(streams), "date_range": f"{min(dates)}..{max(dates)}" if dates else ""}


def _evaluate_file(wiki_root: Path, tier_path: Tuple[str, Path], spec: SearchSpec) -> Optional[Dict[str, Any]]:
    tier, path = tier_path
    text = path.read_text(encoding="utf-8", errors="replace")
    meta = _parse_frontmatter(text, path)
    if not _matches_filters(meta, tier, spec):
        return None
    low_terms = tuple(t.strip().lower() for t in spec.terms if t.strip())
    term_score = _score_doc(meta, low_terms, text.lower()) if low_terms else 10
    if term_score == 0:
        return None
    hits = _collect_line_matches(text.splitlines(), (low_terms, meta["video_id"], meta["body_idx"])) if low_terms else []
    if low_terms and not hits and not any(t in meta["title"].lower() for t in low_terms):
        return None
    return {
        "tier": tier, "score": _TIER_BOOST.get(tier, 0) + term_score + min(len(hits), 8),
        "slug": path.stem, "path": str(path.resolve()), "rel_path": str(path.relative_to(wiki_root)),
        "title": meta["title"], "category": meta["category"] or tier,
        "video_id": meta["video_id"], "upload_date": meta["upload_date"], "tags": meta["tags"],
        "youtube_url": _build_youtube_url(meta["video_id"], hits[0]["seconds"] if hits else None), "matches": hits,
    }


def search_wiki(wiki_root: Path, spec: SearchSpec) -> Dict[str, Any]:
    """Execute deterministic multi-term search across anibon_wiki."""
    has_query = any(t.strip() for t in spec.terms) or bool(spec.tags or spec.category)
    results = [
        entry for tp in (_iter_candidate_files(wiki_root, spec) if has_query else ())
        if (entry := _evaluate_file(wiki_root, tp, spec)) is not None
    ]
    results.sort(key=lambda r: (r["score"], r["upload_date"]), reverse=True)
    return {"terms": list(spec.terms), "total_hits": len(results), "coverage": _wiki_coverage(wiki_root / "wiki"), "results": results[: max(1, spec.limit)]}


def spec_from_json(raw_json: str) -> SearchSpec:
    """Parse JSON query payload supporting nested {date:{from,to}} or flat fields."""
    data = json.loads(raw_json)
    dt = data.get("date") if isinstance(data.get("date"), dict) else {}
    raw_terms = data.get("terms") or ([data["query"]] if data.get("query") else [])
    return SearchSpec(
        terms=tuple(str(t) for t in raw_terms), tags=tuple(str(t) for t in (data.get("tags") or [])),
        category=str(data.get("category") or ""), date_from=str(data.get("date_from") or dt.get("from") or ""),
        date_to=str(data.get("date_to") or dt.get("to") or ""), limit=int(data.get("limit") or 20),
        include_raw=bool(data.get("include_raw", False)),
    )
