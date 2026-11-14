"""Speaker-side transcript mood detector and dual-side (speaker + chat) fusion.

Parses speaker transcript chunks (`.txt`, `.json`, `.xml`, or `.jsonl.gz`
archives) across 7 mood dimensions:
- RAGE_QUIT_PULSE   (rage_quit) : quits/deletes game or ends stream in anger
- ANGRY_TILT_PULSE  (angry)     : sustained swearing + mechanic/boss frustration
- PANIC_SHOCK_PULSE (panic)     : jump-scares, item-loss disasters, boss-arena mishaps
- SICK_AFK_PULSE    (sick_afk)  : stomach pain, illness, or bathroom AFK break
- HYPE_CLUTCH_PULSE (hype)      : clutch survival, boss clear, or jackpot loot celebration
- SLEEPY_DRAIN_PULSE(sleepy)    : late-stream drowsiness/fatigue
"""
from __future__ import annotations

import gzip
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

SWEAR_RE = re.compile(
    r"(ไอ้เหี้ย|ไอเหี้ย|ไอ้เฮี้ย|ไอ้เฮีย|เหี้ยเอ้ย|ควย|ส้นตีน|ปัญญาอ่อน|"
    r"ขี้หมา|หี่มา|ไอ้ห่า|ไอ้สัตว์|ไอสัตว์|ชิบหาย|หน้าหี|หัวควย|ลูกกะหรี่|"
    r"สัตว์นรก|บันละยำ|ระยำ|what the fuck|holy fuck|holy shit|fuck me|fucking)",
    re.IGNORECASE,
)

FRUST_RE = re.compile(
    r"(อารมณ์เสีย|เสียอารมณ์|ลมเสีย|ภารมเสีย|ลงเสีย|อมเสีย|อารมมเสีย|"
    r"อารมณ์ร้อน|เอาลมร้อน|มารมรอน|หัวร้อน|เพียวเรท|หงุดหงิด|เน้องหงิด|กลุ่นหิด|"
    r"โคตรแย่|โคตรเกลียด|เกลียดแม่ง|เกลียดมาก|เกลียดจริง|เกียดบอด|เกียดมาก|กลียดเกม|"
    r"น่ารำคาญ|นารำขาญ|นำลำขาด|รัมคาร|ไม่ถนัด|ไม่เข้าใจโลจิก|ไม่เวิร์คจริง|"
    r"เบื่อชิบหาย|ไม่ไหวว่ะ|ไม่ไหวจริง|ไม่อดทนแล้ว|หมดความอบทน|หมดความอดทน|"
    r"เกมหมา|บอร์ที่หมาจัด|พัดลมเสีย|เกือบพังจอย|คุยงจอย|เขวี้ยงจอย|"
    r"มั่วมาก|มั่วจริง|ไม่มีจังว่าผู้นิช|ไม่มีจังว่ากูตี|อันอยแอดชิต|feel bad)",
    re.IGNORECASE,
)

RAGE_QUIT_RE = re.compile(
    r"(ไม่เล่นแล้ว|ไม่เล่นต่อละ|ไม่เอาแล้ว|ไม่อยากจะเล่นแล้ว|อยากเลิกเล่น|"
    r"หมอดเปลี่ยนเกม|หมอทเปลี่ยนเกม|ลบเกมทิ้ง|จะลบแม่งทิ้ง|อยากจะลบ\s*มันทีง|"
    r"ปิดไลฟ์แบบแย่|fucking hate this game|ช่างแม่งเหอะ|เสียเวลาจริง|"
    r"น่าจะขี้แล้วแม่งจบ|น่าจะขี้แม่งจบ)",
    re.IGNORECASE,
)

SICK_AFK_RE = re.compile(
    r"(ปวดท้อง|ท้องเสีย|ท้องอืด|คำสาปฟาโรห์|คำสัต์ฟาโล|"
    r"โรคกระเพาะ|ปวดขี้|หนีไปขี้|พักเบรกในห้องน้ำ|เล่นรูทวาร)",
    re.IGNORECASE,
)

PANIC_SHOCK_RE = re.compile(
    r"(ตกใจหมด|สะดุ้ง|หัวใจจะวาย|บรรลัยแล้ว|บรรลแล้ว|บรรไล|ชิบหายแล้ว|ชิบหายและ|"
    r"ตายห่าแล้ว|ตายหาแล้ว|ของผมหายหมด|หายวับไปกับตา|missing\s+item|โดนต้ม\s*\d+|"
    r"ไมเกรนขึ้น|ไมเกณฑขึ้น|ทำร้านสู้ของบอสพัง|ทำร้านสู้บอสพัง|ทำรานวอสพัง|"
    r"ระเบิดดัก|เซ็งชิบหาย|มังกรไล่)",
    re.IGNORECASE,
)

HYPE_CLUTCH_RE = re.compile(
    r"(ได้แล้วไอ้เหี้ย|ผ่านแล้วจ้า|ผ่านแล้วกับบอท|รอดแล้ว|ได้ของครบ|"
    r"ได้\s*2\s*อันเลย|โคตรดีเลยว่ะ|ดีจัดเลยครับ|สุดยอดมากเลย)",
    re.IGNORECASE,
)

SLEEPY_DRAIN_RE = re.compile(
    r"(ง่วงแล้วว่ะ|เลือกง่วงแล้ว|เริ่มง่วงแล้ว|ง่วงนอน|ตาจะปิดแล้ว|นอนไม่พอว่ะ)",
    re.IGNORECASE,
)

_TS_PREFIX_RE = re.compile(r"^\s*(?:\(\d{2}:\d{2}:\d{2}\)\s*|\d{2}:\d{2}:\d{2}\s*\|\s*)")


@dataclass
class SpeakerStats:
    """Extracted speaker mood cues from a transcript chunk."""
    n_swears: int = 0
    n_frust: int = 0
    n_rage_quit: int = 0
    n_sick_afk: int = 0
    n_panic_shock: int = 0
    n_hype_clutch: int = 0
    n_sleepy: int = 0
    cues: List[str] = field(default_factory=list)


def dedup_transcript_lines(text: str) -> List[str]:
    """Strip leading timestamps and collapse consecutive identical Whisper lines."""
    cleaned: List[str] = []
    prev_body = ""
    for raw in text.splitlines():
        body = _TS_PREFIX_RE.sub("", raw).strip()
        if not body or body == prev_body:
            continue
        cleaned.append(body)
        prev_body = body
    return cleaned


def _collect_distinct_per_line(pattern: re.Pattern, lines: List[str]) -> List[str]:
    """Collect matches while counting identical stutters on the same line once."""
    hits: List[str] = []
    for line in lines:
        seen = set()
        for match in pattern.findall(line):
            norm = match.lower().strip()
            if norm not in seen:
                seen.add(norm)
                hits.append(match)
    return hits


def parse_speaker_text(text: str) -> SpeakerStats:
    """Extract speaker mood counts and deduplicated cues from raw transcript text."""
    lines = dedup_transcript_lines(text) if text else []
    if not lines:
        return SpeakerStats()
    swears = _collect_distinct_per_line(SWEAR_RE, lines)
    frust = _collect_distinct_per_line(FRUST_RE, lines)
    rage = _collect_distinct_per_line(RAGE_QUIT_RE, lines)
    sick = _collect_distinct_per_line(SICK_AFK_RE, lines)
    panic = _collect_distinct_per_line(PANIC_SHOCK_RE, lines)
    hype = _collect_distinct_per_line(HYPE_CLUTCH_RE, lines)
    sleepy = _collect_distinct_per_line(SLEEPY_DRAIN_RE, lines)
    cues = list(dict.fromkeys(rage + frust + panic + sick + hype + sleepy + swears[:4]))[:8]
    return SpeakerStats(
        n_swears=len(swears), n_frust=len(frust), n_rage_quit=len(rage),
        n_sick_afk=len(sick), n_panic_shock=len(panic),
        n_hype_clutch=len(hype), n_sleepy=len(sleepy), cues=cues,
    )


def _read_chunk_text(chunk_path: Path) -> str:
    """Read raw dialogue text from .txt, .json, or .xml chunk files."""
    if chunk_path.suffix == ".json":
        data = json.loads(chunk_path.read_text(encoding="utf-8", errors="ignore"))
        return "\n".join(it.get("text", "").strip() for it in data.get("items", []) if it.get("text"))
    if chunk_path.suffix == ".xml":
        try:
            root = ET.parse(chunk_path).getroot()
            return "\n".join((el.text or "").strip() for el in root.findall("item") if el.text)
        except ET.ParseError:
            pass
    return chunk_path.read_text(encoding="utf-8", errors="ignore")


def parse_speaker_chunk(chunk_path: Optional[Path]) -> SpeakerStats:
    """Parse one chunk file (.txt/.json/.xml) for speaker mood signals."""
    if not chunk_path or not chunk_path.exists():
        return SpeakerStats()
    return parse_speaker_text(_read_chunk_text(chunk_path))


def classify_speaker_override(sp: SpeakerStats) -> Optional[tuple[str, str, bool]]:
    """Return (verdict, mood, pulse) when speaker mood overrides chat verdict."""
    if sp.n_rage_quit >= 2 or (sp.n_rage_quit >= 1 and (sp.n_frust >= 3 or sp.n_swears >= 8)):
        return ("RAGE_QUIT_PULSE", "rage_quit", True)
    if (
        sp.n_frust >= 4
        or (sp.n_frust >= 2 and sp.n_swears + sp.n_frust >= 6)
        or (sp.n_swears >= 10 and sp.n_frust >= 1)
    ):
        return ("ANGRY_TILT_PULSE", "angry", True)
    if sp.n_sick_afk >= 2:
        return ("SICK_AFK_PULSE", "sick_afk", True)
    if sp.n_hype_clutch >= 3 and sp.n_frust == 0:
        return ("HYPE_CLUTCH_PULSE", "hype", True)
    if sp.n_panic_shock >= 2 and (sp.n_panic_shock >= 3 or sp.n_swears >= 1):
        return ("PANIC_SHOCK_PULSE", "panic", True)
    if sp.n_sleepy >= 1:
        return ("SLEEPY_DRAIN_PULSE", "sleepy", True)
    return None


def resolve_speaker_chunk_path(chunks_dir: Optional[Path], chunk_id: str) -> Optional[Path]:
    """Locate chunks/<chunk_id>.(txt|json|xml) (or zero-padded variant) if present."""
    if not chunks_dir or not chunks_dir.is_dir():
        return None
    m = re.search(r"(\d+)$", chunk_id)
    stems = [chunk_id] + ([f"chunk_{int(m.group(1)):02d}"] if m else [])
    for stem in stems:
        for ext in (".txt", ".json", ".xml"):
            cand = chunks_dir / f"{stem}{ext}"
            if cand.exists():
                return cand
    return None


def load_jsonl_gz_chunks(gz_path: Path, step_sec: int = 270, win_sec: int = 300) -> Dict[str, SpeakerStats]:
    """Slice an archived transcript_<vid>.jsonl.gz into 270s-step chunks and score each."""
    items = []
    with gzip.open(gz_path, "rt", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
    if not items:
        return {}
    n_chunks = (int(items[-1].get("start", 0)) // step_sec) + 1
    out: Dict[str, SpeakerStats] = {}
    for idx in range(n_chunks):
        st, en = idx * step_sec, idx * step_sec + win_sec
        txt = "\n".join(it.get("text", "") for it in items if st <= it.get("start", 0) < en)
        out[f"chunk_{idx:02d}"] = parse_speaker_text(txt)
    return out
