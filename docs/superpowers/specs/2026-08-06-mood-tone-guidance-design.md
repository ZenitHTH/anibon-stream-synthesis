# Design: Mood-Driven Tone Guidance (per-mood hints, AI keeps verb creativity)

Date: 2026-08-06
Status: Approved (guided design)

## Problem

The **Verb Selection Guide** defines 5 Thai verb groups (`Funny/Banter`, `Rant`,
`Shock/Hype`, `Chat`, `News`), each tied to the stream's emotional tone. But the
mood pipeline contradicts it:

- `validate_mood.py` checks *every* PULSE chunk against ONE flat laugh/banter
  whitelist (`แซว/ล้อ/ขำ/ฮา/เม้าท์/...`). A `SHOCK_HYPE_PULSE` or
  `DRAMA_NEWS_PULSE` chunk is wrongly forced to a *laugh* verb. Every mood is
  treated as "funny".
- The whitelist is a **hard rejection** — contradicting the requirement that the
  AI timestamp-writer picks verbs from its own creativity/tone understanding,
  not a programmed verb algorithm.

The guide is intended as *guidance* (top-sheet tells which verb category matches
a sounding, then the AI chooses freely). The pipeline should remind the AI of the
mood/tone, never constrain the verb.

## Design

### 1. `analyze_555.py` — emit a per-chunk `tone` hint (analyzes unchanged)

`serialize()` adds a `tone` field per chunk: a short Thai phrase naming the vibe
+ a `Suggested verb space` the AI **may** draw from. Verb choice stays free.

- Keyed by the chunk's `verdict`/`mood` via an in-script `TONE_HINTS: dict[str, str]`,
  tuned with fuzzy prefix match (e.g. any `*_PULSE` -> map to its family; fall
  back to a generic line for unknown mood).
- Every family (`MEME_PULSE`, `CHAOTIC_MEME_PULSE`, `CUTE_CUNNY_PULSE`,
  `SHOCK_HYPE_PULSE`, `DRAMA_NEWS_PULSE`, `ANGRY_OUTRAGE_PULSE`, ...) gets a hint.
- Non-pulse (`HOT`/`WARM`/`QUIET`) get their own hints too (warm banter / normal
  sampling / free choice).

This is a lightweight `TONE_HINTS` table only; classification logic in
`analyze_555.py` is **unchanged**.

### 2. `validate_mood.py` — guidance-only, no rejection

- Remove `LAUGH_VERBS`, `FLAT_VERBS`, `verb_head()`, and the hard mismatch path
  in `Validator.check()`.
- `Validator` now annotates: for each CULT the chunk's verdict + tone hint and
  whether the timestamp lands in a pulse (non-natural) segment. It **only labels**,
  never fails a stamp.
- `report()` prints the mood + tone per timestamp for the human reviewer. Exit is
  always OK (already the case).

### 3. Tests

- `test_analyze_555_emoji.py`: add assertions that `serialize()` emits a
  non-empty `tone` for PUL, HOT/WARM/QUIET, and that `TONE_HINTS` covers every
  mood present in `resources/emoji_dictionary.json` (no gap / no fallback
  silently used for known family).
- New `validate_mood` test: a flat factual verb (e.g. `อธิบาย`) inside a
  SHOCK_HYPE_PULSE chunk is **allowed** (no flag), proving rejection is off.

## Out of scope (YAGNI)

- No parent program-side verb whitelist or rejection anywhere in the pipeline.
- No change to the emoji dictionary.
- No new Python module — `TONE_HINTS` lives inline in `validate_mood`'s consumer
  source `/` or a small `resources/tone_hints.json` only if a shared consumer
  emerges. (Default: inline.)

## Tone-hint wording
Authored by Gemini 3.6 (the LLM preferred for Thai mood/tone nuance), capturing
the Thai verb-group vibe for each mood family. Final wording captured during
implementation.

## Testing
- pytest `tests/` (existing 40) must stay green.
- Manual: `analyze_555 --out` on a known pulse chunk -> `tone` present; 
  `validate_mood` on the same output => no flags.