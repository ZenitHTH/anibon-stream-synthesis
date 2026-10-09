"""Multi-resolution stream topic anchor & mid-stream pivot scanner.

Provides:
- Global Macro Anchor extraction from metadata (info.json)
- Dynamic Rolling Chunk topic pivot detection for variety streams ('ไปเรื่อย')
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

FRANCHISE_MARKERS = {
    "Zelda: Breath of the Wild": ["zelda", "botw", "breath of the wild", "เซลด้า", "วารูตะ", "ไฮรูล", "ไซดอน"],
    "Fate/Grand Order": ["fgo", "fate/grand order", "fate grand order", "เฟส grand", "กูดะกูดะ", "ordeal call"],
    "Yu-Gi-Oh": ["yugioh", "ygo", "ยูกิ", "master duel", "มาสเตอร์ดูเอล", "จัดเด็ค"],
    "Pokémon": ["pokemon", "pokémon", "โปเกมอน", "radical red", "ปิกาจู", "สวิตช์ 2"],
    "Limbus Company": ["limbus", "limbus company", "ริมัส", "ิม company", "canto", "คันเ 10", "พีมูน", "project moon"],
    "Genshin Impact": ["genshin", "เกนชิน", "snezhnaya", "nod-krai"],
    "Honkai: Star Rail": ["hsr", "star rail", "สตาร์เรล"],
    "Tokusatsu": ["tokusatsu", "โทคุ", "ไรเดอร์", "project r.e.d", "กาบัน", "zeztz"],
    "One Piece": ["one piece", "oneพiece", "วันพีซ"],
    "Bleach": ["bleach", "บลีช", "tybw", "สงครามเลือดพันปี"],
}


def extract_macro_anchor(info_data: Optional[Dict[str, Any]]) -> Optional[str]:
    """Extract primary franchise anchor from stream metadata (info.json)."""
    if not info_data:
        return None

    title = str(info_data.get("title", "")).lower()
    desc = str(info_data.get("description", "")).lower()
    tags = " ".join(str(t).lower() for t in info_data.get("tags", []))
    combined = f"{title} {tags} {desc[:300]}"

    for franchise, markers in FRANCHISE_MARKERS.items():
        if any(m in combined for m in markers):
            return franchise

    return None


def scan_chunk_topic_pivot(
    chunk_text: str,
    current_anchor: Optional[str] = None,
) -> Optional[str]:
    """Scan transcript chunk for mid-stream franchise pivots differing from current anchor."""
    if not chunk_text:
        return None

    text_lower = chunk_text.lower()
    current_markers = FRANCHISE_MARKERS.get(current_anchor, []) if current_anchor else []

    for franchise, markers in FRANCHISE_MARKERS.items():
        if franchise == current_anchor:
            continue
        # Require match of non-current franchise marker
        hit = any(re.search(rf"\b{re.escape(m)}\b", text_lower) if m.isascii() else m in text_lower for m in markers)
        if hit:
            return franchise

    return None


def build_stream_topic_profile(
    workspace: Path,
    signals_map: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build unified stream topic profile combining macro anchor and chunk signals."""
    workspace = Path(workspace)
    info_file = workspace / "info.json"
    info_data = None
    if info_file.is_file():
        try:
            info_data = json.loads(info_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    macro_anchor = extract_macro_anchor(info_data)
    pivots: Dict[str, str] = {}

    if signals_map:
        for chunk_id, sig in signals_map.items():
            if not isinstance(sig, dict):
                continue
            matched_kw = sig.get("matched_keywords", {})
            kw_str = " ".join(matched_kw.keys()) if isinstance(matched_kw, dict) else ""
            pivot = scan_chunk_topic_pivot(kw_str, macro_anchor)
            if pivot:
                pivots[chunk_id] = pivot

    return {
        "macro_anchor": macro_anchor,
        "pivot_chunks": pivots,
    }
