# Automated Media-vs-Streamer Separation System Specification

## 1. Intent & Why
When Pu Boat plays songs, meme clips, or videos on stream (e.g., อ.ไม้ร่ม *"พี่ไม่รักน้องเจ้า"*, *"เราจะทำตามสัญญา"*, *"เพลงมหาจุฬาลงกรณ์"*), YouTube Auto-Captions and Whisper merge song lyrics or video dialogue directly into the transcript alongside Boat's spoken interjections and gameplay commentary. Furthermore, Thai ASR severely garbles traditional singing/vocal melisma (e.g., `"พี่ไม่รักน้องเจ้า"` $\rightarrow$ `"ผีไม่ได้ดักเจ้า"`). Without automated separation, local LLMs (`gemma-4-12b`) hallucinate that Boat himself spoke the garbled lyrics or misinterpret the stream's topic.

## 2. Goals & Non-Goals
- **Goals**:
  1. **Zero-Cost Event Trigger (`media_trigger.py`)**: Scan chunks and aligned LiveChat in `< 0.1s` using deterministic heuristics (`>>` turn-taking density, music tags, Boat media-intent cues, and LiveChat song-query bursts) so unaffected chunks incur zero overhead.
  2. **Automated Media & Lyric Discovery (`media_identifier.py`)**: Extract candidate song/video titles from LiveChat crowd-sourcing and transcript intro phrases, match against a local canonical media catalog (`resources/media_catalog.json`) with optional stdlib DuckDuckGo HTML fallback, and retrieve canonical lyrics/scripts.
  3. **Line & Intra-Line Separation (`media_separator.py`)**: Classify each transcript line (and split mid-line collisions where lyrics and Boat speech merge) into `BOAT_SPEECH`, `BOAT_GAMEPLAY`, or `MEDIA_AUDIO (<Title>)` using Thai phonetic skeleton similarity (consonant + vowel + tone-stripped skeleton matching for ASR garbles), speaker-turn markers (`>>`), Boat interjection markers, and active gameplay vocabulary.
  4. **Seamless Pipeline Integration**: Inject a compact, deterministic `## DETECTED MEDIA & LYRIC SEPARATION` ground-truth block into `build_recursive_prompt()` and `build_group_prompt()` so `process_chunks_local.py` automatically separates songs from Boat's speech on every run.
- **Non-Goals**:
  - No heavy external Python dependencies (`torch`, `demucs`, `pyannote`, `pytest`). Must run 100% on Python 3.10+ stdlib (`unittest`, `difflib`, `re`, `json`, `urllib`).
  - No modifications to `skills/` directory count (preserve 22 skills).

## 3. Constraints
- **Clean Code Rules**: Max 200 lines per file, max 20 lines per function, max 3 arguments per function (group 3+ parameters into `@dataclass(frozen=True)` config/context objects), no boolean flag arguments, guard clauses first ($\le 2$ indentation levels).
- **Repo Invariants**: Every module using PEP 604/585 type annotations MUST include `from __future__ import annotations`. All tests MUST use `unittest` (zero `pytest` imports).
