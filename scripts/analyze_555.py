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
                             mood, verdict}

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


def _load_emoji_dictionary(path: Optional[Path] = None) -> Dict[str, bool]:
    """Load emote->laugh-intent map from resources/emoji_dictionary.json.

    Returns {emote_code: is_laugh_marker}. Missing/absent file degrades to an
    empty map (no named emote counts as a laugh marker).
    """
    res = path or (Path(__file__).resolve().parent.parent / "resources" / "emoji_dictionary.json")
    try:
        data = json.load(open(res, encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {code: info.get("laugh", False)
            for code, info in data.get("emotes", {}).items()}


# emote_code -> is_laugh (case-sensitive as authored in the dictionary)
LAUGH_EMOTES: Dict[str, bool] = _load_emoji_dictionary()


def _is_laugh_emote(message: str) -> bool:
    """True if the message contains any dictionary-confirmed laugh emote."""
    for code, laugh in LAUGH_EMOTES.items():
        if laugh and code in message:
            return True
    return False


@dataclass(frozen=True)
class Config:
    """Tunable detection thresholds (Stage 2 hyperparameters)."""
    # markers needed in one bucket to call a MEME_PULSE
    pulse_threshold: int = 12
    # per-chunk minimum markers for the "hot" flag regardless of bucket
    hot_min: int = 14
    # for low-message chunks (< low_msg) absolute counts understate bursts:
    # use marker density >= low_msg_density as the pulse signal instead
    low_msg: int = 100
    low_msg_density: float = 0.20
    # bucket width for peak-window detection (seconds)
    bucket: int = 90
    # how many high buckets can be reported
    max_peaks: int = 4


@dataclass
class ChatStats:
    """Parsed signals from a single chunk's chat log."""
    n_markers: int = 0
    n_messages: int = 0
    # (window_start_sec, window_end_sec, marker_count) desc by marker count
    peak_windows: List[Tuple[int, int, int]] = field(default_factory=list)


def to_sec(hh: str, mm: str, ss: str) -> int:
    return int(hh) * 3600 + int(mm) * 60 + int(ss)


def parse_chat(path: Path) -> ChatStats:
    """Stage 2a: time-window the log and count 555/laugh markers + all msgs."""
    marker_secs: List[int] = []
    all_secs: List[int] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = TS_RE.search(line)
            if not m:
                continue
            all_secs.append(to_sec(*m.groups()))
            if _is_laugh(line):
                marker_secs.append(to_sec(*m.groups()))
    return ChatStats(n_markers=len(marker_secs), n_messages=len(all_secs),
                     peak_windows=_find_peaks(marker_secs))


def _is_laugh(line: str) -> bool:
    """True if a chat line is a laugh marker: 555/words, unicode laugh emojis,
    or a dictionary-confirmed laugh emote. Flat/AFK/confusion/political emotes
    are NOT markers."""
    if LAUGH_RE.search(line):
        return True
    # unicode laugh codepoints / ☠ / +1 always count
    for ch in EMOJI_CODEPOINTS + "\u2620":
        if ch in line:
            return True
    if "+1" in line:
        return True
    return _is_laugh_emote(line)


def _find_peaks(marker_secs: List[int], bucket: int = 90, max_peaks: int = 4
                ) -> List[Tuple[int, int, int]]:
    """Stage 2b: bucket markers and rank the liveliest windows (desc count)."""
    if not marker_secs:
        return []
    buckets: "defaultdict[int, List[int]]" = defaultdict(list)
    for s in marker_secs:
        buckets[s // bucket].append(s)
    rows = []
    for k, times in buckets.items():
        rows.append((k * bucket, k * bucket + bucket, len(times)))
    rows.sort(key=lambda r: r[2], reverse=True)
    return rows[:max_peaks]


@dataclass
class Verdict:
    """Stage 2c: classification of one chunk's mood."""
    verdict: str
    mood: str
    pulse: bool


def classify(stats: ChatStats, cfg: Config) -> Verdict:
    """Stage 2c: turn parsed chat signals into a mood verdict."""
    n_msgs = stats.n_messages
    n_markers = stats.n_markers
    density = n_markers / n_msgs if n_msgs else 0.0
    peak_thresh = stats.peak_windows[0][2] if stats.peak_windows else 0
    low_msg_pulse = n_msgs < cfg.low_msg and density >= cfg.low_msg_density
    has_peak_burst = peak_thresh >= cfg.pulse_threshold or low_msg_pulse
    if has_peak_burst:
        return Verdict("MEME_PULSE", "funny", True)
    if n_markers >= cfg.hot_min:
        return Verdict("HOT", "warm", False)
    if n_markers >= 1:
        return Verdict("WARM", "warm", False)
    return Verdict("QUIET", "neutral", False)


def fmt_ts(sec: int) -> str:
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def serialize(stats: ChatStats, verdict: Verdict, cfg: Config) -> dict:
    """Build the on-disk JSON record for one chunk (schema for validate_mood.py)."""
    density = stats.n_markers / stats.n_messages if stats.n_messages else 0.0
    peak_windows = [
        {"start": fmt_ts(a), "end": fmt_ts(b), "count": c}
        for a, b, c in stats.peak_windows
        if c >= cfg.pulse_threshold
    ]
    return {
        "density": round(density, 3),
        "n_markers": stats.n_markers,
        "n_messages": stats.n_messages,
        "pulse": verdict.pulse,
        "verdict": verdict.verdict,
        "mood": verdict.mood,
        "peak_windows": peak_windows,
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