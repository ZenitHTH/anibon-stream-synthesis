#!/usr/bin/env python3
"""Detect Thai-laugh / meme pulses from aligned LiveChat logs.

Thai watchers mark laughter with "555..." (and the "5" family), "xD", "haha",
"ฮา", "ขำ", "555555...". A pulse = clustered burst of these markers within a
short window. This is the only reliable laugh proxy when the autotranscript
cannot hear the streamer actually laughing (audio unclear / no laugh glyph).

This script is downstream of align_live_chat.py: it reads per-chunk LiveChat
logs (the same files the timestamper subagents read) and emits a JSON verdict
that the subagent prompt must weight when writing mood-bearing descriptions.

Pipeline follows the "Dual-Side Thai Stream & Chat Mood Detection" design doc
Stage 2 (Live Chat Pulse Processing):
  time windowing/chunking -> message velocity -> 555/laugh-marker filter -> verdict.

Input:   --livechat  dir of per-chunk chat logs (livechat/livechat_chunk_*.txt)
         --index     livechat_index.json  (chunk name -> file), optional
         --out       output json path
Output:  JSON dict chunk -> {density, n_markers, n_messages, peak_windows,
                             mood, verdict, tone}

Heuristic verdicts:
  - QUIET        low chat, no burst            -> neutral mood, normal sampling
  - MEME_PULSE   strong burst (count >= pulse) -> funny/meme mood: laugh firstverb
  - WARM         some markers, no burst        -> light banter, optional laugh verb

Peak windows are computed by sliding a BUCKET seconds bucket over the sorted
message timestamps and finding buckets with the most laugh markers.
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

LAUGH_RE = re.compile(r"(5{3,}|[xX][dD]{1,}|haha+|ฮา+|ขำ+|\blol\b|\bhaha\b)", re.IGNORECASE)
# Stage 2.5-2.7: Unicode laugh emojis, Anibon custom emotes (:_Name:)_ and
# YouTube global emotes (:word-word:) count as peer laugh markers even when a
# message has no 5 5 5 text. 💀/☠/🤡 are "ตายแป๊บ"/"ลั่น" (dead laughing) in Thai
# subculture, not sadness; 😭 here means "ขำจนร้องไห้", not crying.
EMOJI_CODEPOINTS = (
    "\U0001F602" "\U0001F923" "\U0001F480" "\U0001F921" "\U0001F62D"
    "\U0001F525" "\U0001F5A4" "\U0001F451" "\U0001F44D"
)
EMOJI_MARKER_RE = re.compile(
    rf"([{re.escape(EMOJI_CODEPOINTS)}\u2620]|:[A-Za-z_][A-Za-z0-9_]*:|\+1)"
)
TS_RE = re.compile(r"\[(\d{2}):(\d{2}):(\d{2})\]")


def _load_emoji_dictionary(path: Optional[Path] = None) -> Dict[str, dict]:
    """Load emote->{mood, weight} map from resources/emoji_dictionary.json."""
    res = path or (Path(__file__).resolve().parent.parent / "resources" / "emoji_dictionary.json")
    try:
        data = json.load(open(res, encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {code: info for code, info in data.get("emotes", {}).items()}


# emote_code -> {mood, weight, laugh} (case-sensitive as authored in the dictionary)
EMOTE_INFO: Dict[str, dict] = _load_emoji_dictionary()


def _load_tone_hints(path: Optional[Path] = None) -> Dict[str, dict]:
    """Load mood->{tone, verbs} guidance map from resources/tone_hints.json."""
    res = path or (Path(__file__).resolve().parent.parent / "resources" / "tone_hints.json")
    try:
        data = json.load(open(res, encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data.get("hints", {})


# mood family -> {tone, verbs} — Thai guidance for the timestamp writer. The AI
# draws from the verbs freely; this is a reminder of the mood, not a rule.
TONE_HINTS: Dict[str, dict] = _load_tone_hints()

FALLBACK_TONE = {
    "tone": "เขียนตามอารมณ์ของเหตุการณ์",
    "verbs": ["แซว", "วิเคราะห์", "สรุป"],
}


@dataclass(frozen=True)
class Config:
    """Tunable detection thresholds (Stage 2 hyperparameters)."""
    pulse_score: float = 10.0   # weighted score needed in one bucket for a pulse
    hot_min: float = 12.0       # chunk-wide weighted score for the hot flag
    bucket: int = 90            # bucket width for peak-window detection (seconds)
    max_peaks: int = 4          # how many high buckets can be reported


@dataclass
class ChatStats:
    """Parsed signals from a single chunk's chat log."""
    n_markers: int = 0
    n_messages: int = 0
    n_start: int = 0
    n_secs: int = 0
    # (window_start_sec, window_end_sec, score, dominant_mood)
    peak_windows: List[Tuple[int, int, float, str]] = field(default_factory=list)


def to_sec(hh: str, mm: str, ss: str) -> int:
    return int(hh) * 3600 + int(mm) * 60 + int(ss)


def _emote_moods(line: str) -> List[Tuple[str, float]]:
    """Laugh-mood->weight for every laugh-flagged emote present in the line.

    Non-laugh emotes (flat/AFK/political/confusion) carry a mood but do NOT
    drive a pulse — they belong to other pipelines (masking-royal-news etc).
    """
    out = []
    for code, info in EMOTE_INFO.items():
        if info.get("laugh") and code in line:
            out.append((info["mood"], info["weight"]))
    return out


def parse_chat(path: Path) -> ChatStats:
    """Stage 2a: time-window the log, weight 555/laugh markers + all msgs.

    Weighting follows the design doc Stage 2.5/2.6: unicode laugh emojis and
    custom emotes carry a weight (1.5/1.2/1.0 or the dictionary weight); plain
    555/text laughs count 1.0. A line is not a simple binary marker — it
    contributes its weighted score and mood to the bucket it falls in.
    """
    all_secs: List[int] = []
    score_secs: List[Tuple[int, float, str]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = TS_RE.search(line)
            if not m:
                continue
            s = to_sec(*m.groups())
            all_secs.append(s)
            for mood, w in _line_signals(line):
                score_secs.append((s, w, mood))
    return ChatStats(n_markers=len(score_secs), n_messages=len(all_secs),
                     n_start=min(all_secs) if all_secs else 0,
                     n_secs=max(all_secs) if all_secs else 0,
                     peak_windows=_find_peaks(score_secs))


def _line_signals(line: str) -> List[Tuple[str, float]]:
    """Weighted (mood, score) contributions for a chat line (Stage 2.5/2.7).

    Prioritises specific emote moods over the generic 555 lump. Flat / AFK /
    confusion / political emotes still contribute their mood but do not drive a
    chunk to MEME_PULSE unless the emote itself is a laugh verity."""
    moods = _emote_moods(line)
    if LAUGH_RE.search(line):
        moods.append(("MEME_PULSE", 1.0))
    for ch in EMOJI_CODEPOINTS + "\u2620":
        if ch in line:
            moods.append(("MEME_PULSE", 1.0))
    if "+1" in line:
        moods.append(("MEME_PULSE", 1.0))
    return moods


def _find_peaks(score_secs: List[Tuple[int, float, str]], bucket: int = 90,
                max_peaks: int = 4) -> List[Tuple[int, int, float, str]]:
    """Stage 2b: bucket weighted scores and rank the liveliest windows."""
    if not score_secs:
        return []
    buckets: "defaultdict[int, List[Tuple[float, str]]]" = defaultdict(list)
    for s, w, mood in score_secs:
        buckets[s // bucket].append((w, mood))
    rows = []
    for k, items in buckets.items():
        score = round(sum(w for w, _ in items), 3)
        moods: "defaultdict[str, float]" = defaultdict(float)
        for w, mood in items:
            moods[mood] += w
        dominant = max(moods, key=moods.get)
        rows.append((k * bucket, k * bucket + bucket, score, dominant))
    rows.sort(key=lambda r: r[2], reverse=True)
    return rows[:max_peaks]


@dataclass
class Verdict:
    """Stage 2c: classification of one chunk's mood."""
    verdict: str
    mood: str
    pulse: bool


def classify(stats: ChatStats, cfg: Config) -> Verdict:
    """Stage 2c: turn parsed chat signals into a mood verdict.

    A pulse = a 90s bucket whose weighted score clears cfg.pulse_score. The
    verdict takes the dominant emote/555 mood of the top bucket (e.g. MEME_PULSE
    for a 555 flood, CUTE_CUNNY_PULSE for a :_CunnyBoat: flood). No density
    shortcut — the weighted score is the single source of truth, so verdict and
    segments always agree."""
    pulse_buckets = [p for p in stats.peak_windows if p[2] >= cfg.pulse_score]
    if pulse_buckets:
        _, _, _, mood = max(pulse_buckets, key=lambda p: p[2])
        return Verdict(mood, mood.lower(), True)
    if stats.n_markers >= cfg.hot_min:
        return Verdict("HOT", "warm", False)
    if stats.n_markers >= 1:
        return Verdict("WARM", "warm", False)
    return Verdict("QUIET", "neutral", False)


def tone_hint(verdict: str) -> dict:
    """Return the Thai tone guidance {tone, verbs} for a verdict (fallback safe).

    Looks up by exact verdict name; falls back to the generic hint when the mood
    family is unmapped so a new emote never crashes serialization."""
    hit = TONE_HINTS.get(verdict)
    if hit:
        return {"tone": hit.get("tone", FALLBACK_TONE["tone"]),
                "verbs": hit.get("verbs", FALLBACK_TONE["verbs"])}
    return {"tone": FALLBACK_TONE["tone"], "verbs": FALLBACK_TONE["verbs"]}


def fmt_ts(sec: int) -> str:
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def build_segments(stats: ChatStats, cfg: Config) -> List[dict]:
    """Per-chunk mood segments: pulse windows + the natural gaps around.

    Pulse windows carry their dominant mood; the gaps collapse into natural
    spans. Filters peaks at/above pulse_score. Empty at no qualifying peak."""
    peaks = sorted([p for p in stats.peak_windows if p[2] >= cfg.pulse_score])
    segs: List[dict] = []
    cursor = stats.n_start
    for start, end, _, mood in peaks:
        if start > cursor:
            segs.append({"start": fmt_ts(cursor), "end": fmt_ts(start), "mood": "natural"})
        segs.append({"start": fmt_ts(start), "end": fmt_ts(end), "mood": mood.lower()})
        cursor = end
    if cursor < stats.n_secs:
        segs.append({"start": fmt_ts(cursor), "end": fmt_ts(stats.n_secs), "mood": "natural"})
    return segs


def serialize(stats: ChatStats, verdict: Verdict, cfg: Config) -> dict:
    """Build the on-disk JSON record for one chunk (schema for validate_mood.py)."""
    density = stats.n_markers / stats.n_messages if stats.n_messages else 0.0
    peak_windows = [
        {"start": fmt_ts(a), "end": fmt_ts(b), "score": c, "mood": m}
        for a, b, c, m in stats.peak_windows
        if c >= cfg.pulse_score
    ]
    return {
        "density": round(density, 3),
        "n_markers": stats.n_markers,
        "n_messages": stats.n_messages,
        "pulse": verdict.pulse,
        "verdict": verdict.verdict,
        "mood": verdict.mood,
        "tone": tone_hint(verdict.verdict),
        "peak_windows": peak_windows,
        "segments": build_segments(stats, cfg),
    }


def resolve_chunk_name(chat_path: Path, index: dict) -> str:
    """Stage 1b: map a livechat file back to its chunk id via the index."""
    for name, info in index.items():
        rel = info["file"] if isinstance(info, dict) else info
        if Path(rel).name == chat_path.name:
            return name
    return chat_path.stem.replace("livechat_chunk_", "chunk_")


def load_index(index_path: str) -> dict:
    if not index_path or not Path(index_path).exists():
        return {}
    return json.load(open(index_path, encoding="utf-8"))


def analyze(livechat_dir: str, index_path: str, out_path: str,
            cfg: Optional[Config] = None) -> dict:
    """Full pipeline: parse every chunk log, classify, write mood_555.json."""
    cfg = cfg or Config()
    index = load_index(index_path)
    result = {}
    for f in sorted(Path(livechat_dir).glob("livechat_chunk_*.txt")):
        chunk = resolve_chunk_name(f, index)
        stats = parse_chat(f)
        verdict = classify(stats, cfg)
        result[chunk] = serialize(stats, verdict, cfg)
    json.dump(result, open(out_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    # report
    print(f"chunks analyzed: {len(result)}")
    memes = [k for k, v in result.items() if v["verdict"] == "MEME_PULSE"]
    print(f"MEME_PULSE chunks ({len(memes)}): {sorted(memes, key=lambda c: int(c.split('_')[1]))}")
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--livechat", required=True)
    ap.add_argument("--index", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    analyze(a.livechat, a.index, a.out)
    return 0


if __name__ == "__main__":
    main()