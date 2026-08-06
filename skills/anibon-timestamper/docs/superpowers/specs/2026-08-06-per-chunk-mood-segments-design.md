# Per-Chunk Mood Segments

Date: 2026-08-06

## Problem

`mood_555.json` emits ONE flat `verdict`/`mood` per chunk (analyze_555.py:197).
A chunk mixing emotions (e.g. funny burst in the middle of natural talk) collapses
to a single label, so `validate_mood.py` forces every timestamp in a `MEME_PULSE`
chunk to open with a laugh verb — mislabeling the natural parts.

## Approach

A) Marker-density only: segment mood derives solely from chat 555/burst windows.

## Changes

### analyze_555.py
- Add `chunk_end` (max message timestamp) to `ChatStats`.
- `serialize()` adds `segments`: a time-ordered list built from `peak_windows`
  (only peaks with `count >= pulse_threshold` = `funny`) plus the quiet gaps
  around them (`natural`). Adjacent quiet gaps merge. Keep flat `verdict`/`mood`
  for back-compat.

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
