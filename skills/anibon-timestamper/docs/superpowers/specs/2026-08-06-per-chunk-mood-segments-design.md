# Per-Chunk Mood Segments

Date: 2026-08-06

## Problem

`mood_555.json` emits ONE flat `verdict`/`mood` per chunk (analyze_555.py:197).
A chunk mixing emotions (e.g. funny burst in the middle of natural talk) collapses
to a single label, so `validate_mood.py` forces every timestamp in a `MEME_PULSE`
chunk to open with a laugh verb — mislabeling the natural parts.

## Approach

A) Marker-density only: segment mood derives solely from chat 555/burst windows.

### Revision 2026-08-06 (after the "looks weird" fix)

The first cut had two burst definitions fighting (bucket-count vs low-msg density),
so verdict said MEME_PULSE while segments stayed all-natural, and a single 555 in a
3-msg chunk over-triggered. Aligned to the Dual-Side design doc instead:

- **Weighted scoring** replaces binary marker-count: text 555 = 1.0, unicode laugh
  emoji = 1.0, and laugh-flagged custom emotes use their dictionary weight (per
  emoji_dictionary.json). Non-laugh emotes (flat/AFK/political/confusion) carry a
  mood but never drive a pulse.
- **Real verdicts** — a pulse bucket's dominant mood is the verdict (MEME_PULSE,
  CHAOTIC_MEME_PULSE, CUTE_CUNNY_PULSE, ...). Density low-msg shortcut removed.
- **Segments always agree with verdict** because both come from the same weighted
  peak buckets.

## Changes

### analyze_555.py
- Add `chunk_end` (max message timestamp) to `ChatStats`.
- `parse_chat`/`_line_signals` produce weighted (mood, score) signals instead of
  boolean markers.
- `_find_peaks` buckets weighted scores, tracks dominant mood per bucket.
- `classify` takes the top qualifying bucket's mood as verdict (no density path).
- `serialize()` adds `segments`: time-ordered `natural`/`<mood>` spans from the
  qualifying peaks + quiet gaps. Keep flat `verdict`/`mood` for back-compat.

Schema:
```json
"chunk_07": {
  "verdict": "MEME_PULSE",
  "mood": "funny",
  "segments": [
    {"start":"00:00:00","end":"00:00:40","mood":"natural"},
    {"start":"00:00:40","end":"00:01:10","mood":"funny"},
    {"start":"00:01:10","end":"00:02:00","mood":"natural"}
  ]
}
```

### validate_mood.py
- `Validator.check()` requires laugh verb only when: chunk verdict is `MEME_PULSE`
  AND the stamp falls inside a `funny` segment. Stamp in a `natural` segment →
  flat verb allowed. Fall back to whole-chunk behavior when `segments` absent
  (old mood files / no peaks).

## Edge cases
- No peaks → single all-natural segment, nothing enforced.
- `segments` absent → unchanged behavior.

## Testing
- Extend `scripts/test_analyze_555_emoji.py` or add assert self-check for
  segment building (mixed chunk → correct natural/funny split).
- Run both scripts on a fixture.
