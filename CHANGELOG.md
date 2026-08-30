# Changelog

All notable changes to **anibon-stream-synthesis** are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/). Versioning follows [Semantic Versioning](https://semver.org/).

## [1.2.2] — 2026-08-30

### Added
- **Visual Activity & Webcam Grounding (`anibon-stream-activity`)** — Added storyboard unpacking (`sb3`/`sb2` sprite sheets) with tile cropping (`unpack_storyboard.py`), activity & webcam presence/AFK/face expressions timeline extractor (`extract_activity.py`), and chunk activity aligner (`align_chunk_activity.py`) integrated into `anibon-timestamper` orchestrator and chunk subagents.
- **Global Vlog, Convention, and Book Fair Support** — Added dedicated taxonomy, parsing, and tone guidelines for off-stream vlogs, book fairs, and anime/gaming conventions.
- **Whisper Corruption Recovery Enhancement** — Added multi-GPU worker pool support and thread tuning in `fix_hallucinations.py` for accelerated Whisper repetition loop recovery.
- **Vision-Assisted Notes & Storyboard Inspection** — Added lightweight storyboard (`sb0`) frame extraction to `antigravity-vision-proxy` and Step 2.5 vision inspection into `anibon-garbled-notes` for visual resolution of doubting words.
- **Version 2 Grouped Garbled Dictionary Schema** — Restructured `garbled_replacements.json` from flat 1:1 list to canonical-target grouped schema (`mappings: { "CanonicalWord": ["pattern1", "pattern2"] }`), expanding across anime, gaming, and Thai subculture slang.
- **`update_garbled_dictionary.py` Automation Tool** — Added automated CLI and library tool in `cleaning-auto-transcripts` supporting `--from-raw-dir`, `--from-notes`, `--add`, and multi-file atomic synchronization across root and skill resources.
- **Root Resource Priority** — Updated `resource_path()` across all modules to prioritize master root `resources/` over local shadow copies.
- **Non-Spoiler Gacha Policy & Game Content Updates** — Enforced non-spoiler gacha policy in prompt templates and updated Zenless Zone Zero character/content reference to v3.1.

### Changed
- `clean_garbled_english.py` updated to compile grouped mappings with descending pattern length precedence and backward compatibility.
- `anibon-timestamper/SKILL.md` (Step 8.6), `cleaning-auto-transcripts/SKILL.md`, and `anibon-garbled-notes` agent specifications updated for automated dictionary growth.
- Hardened None webcam handling, preserved facial expressions, slide sampling, and chunk deduplication in activity analysis.
- Title collision guardrails and sanitized default mappings added.

---

## [1.2.1] — 2026-08-14

### Added
- **Multilingual Pokémon Relational Database (`pokemon.db`)** — Built relational SQLite database containing 1,025 Pokémon species (Gens 1–9) mapped across EN, JA (Kana), official TPC Japanese-phonetic Thai (`name_th_official`), and community English-sound Thai / streamer nicknames (`name_th_english_sound`).
- **`fetch_pokemon_db.py` Bootstrap Script** — Zero-setup SQLite builder script (`skills/anibon-world-identity/scripts/fetch_pokemon_db.py`) supporting `--check`, `--force`, and `--db` flags for fast <5ms preflight checks.
- **Mandatory Thai Pokémon Naming Rules** — Enforced Thai primary display formatting (`แบกซ์แคลิเบอร์ (Baxcalibur)`, `ม้าดำ (Spectrier)`) across `anibon-world-identity/SKILL.md` for all Pokémon stream timestamps and entity lookups.
- **Expanded Garbled-Word Dictionary** — Grown `resources/garbled_replacements.json` to 144 regex replacement rules (added 50 new Thai-Latin ASR proper noun corrections).

### Changed
- `anibon-world-identity` SKILL.md updated with strict dual-system lookup instructions prioritizing community Thai names.

---

## [1.2.0] — 2026-08-13

### Added
- **Garbled-Word Feedback Loop** — chunk subagents emit `GARBLED_NOTES:` blocks for Thai-Latin hybrids that survive cleaning; new `anibon-garbled-notes` subagent consolidates them, writes `garbled_notes.json` (Step 8.6), and appends confirmed rules to the shared `garbled_replacements.json`. Dictionary auto-grows each stream via `resource_path()` (now 94 rules).
- **Mood-Driven Tone Pipeline** — `analyze_555.py` emits per-chunk mood segments from emote-weighted LiveChat scoring; `validate_mood.py` verifies mood-bearing timestamps honour verdicts; Thai mood hints injected into subagent prompts (AI keeps verb creativity).
- **Named Subagents** — `anibon-chunk-timestamper`, `anibon-garbled-notes`, `anibon-summarizer` as first-class agents wired into the pipeline; never generic Task/self agents.
- **NO GAPS Enforcement** — `audit_gaps.py` + agent guardrails enforce the max-10-min gap rule with gap→chunk mapping.
- **Subagent Batching** — MAX 6 concurrent subagents via `batching-subagents-concurrency` skill.
- **Group-of-Chunks Model** — subagents process 4–5 chunks per group for topic continuity; prompt template fully adapted.
- **LiveChat Psychology & Mood Rules** — emote-intent laugh detection, granular high-meme rules, full-list reveal across adjacent chunks.

### Changed
- `garbled_replacements.json` resolved via `resource_path()` up to plugin root — fixes stale-shadow bug where per-skill copies hid the full dictionary.
- `detect_signals.py` / `clean_garbled_english.py` support XML chunk format.
- Mood segment start uses chunk first chat ts (not 00:00:00).
- Emoji surfaced as plaintext for chat parsing + emote-aware mood.
- Windows compatibility + chunk-reader helper in timestamper.
- Skills restructured per official plugin anatomy; structure tests added.

### Fixed
- Removed invalid `tools` field from agent frontmatter; banned raw-transcript pasting in chunk-timestamper; synced OpenCode/Antigravity agent copies.
- Weighted emote scoring with real verdicts and self-consistent segments.

---

## [1.1.4] — 2026-07-31

### Added
- **Standalone `npx skills` support** — bundled `anibon` Python package into each skill's `scripts/anibon/` (zero-setup single-skill install).
- **Whisper Corruption Recovery** — BFS parallel divide-and-conquer (`fix_hallucinations.py`) with 30s base case and multi-sentence loop scanner.
- **Vision Proxy Frame Extraction** — `enrich_uncertain_with_vision.py` extracts frames at `[?]` uncertain timestamps.
- **Multithreaded `detect_signals.py`** — hardware-adaptive keyword matching.
- **Channel & Nickname Knowledge** — `@MonthonKri` (พี่โต๊ะ) mapping + collab history in `resources/channels.json`.
- **Knowledge Base Expansion** — Blue Archive, Dinoblade, Sekiro, IRL Vlog `[Food]`/`[Shopping]` lore keywords.

### Fixed
- Strict word-boundary matching in topic classifier; XML chunk support in `detect_signals.py`.
- Garbled-English post-processing in `pack_timestamps.py`.
- Relative (not absolute) paths in SKILL.md.

---

## [1.1.3] — 2026-07-25

### Added
- **Context-first balanced partition** in `pack_timestamps.py` — replaces greedy with context-aware packing.
- **`TAG_MACRO_MAP`** — groups `[Talk]`/`[Reaction]`/`[Chat]` into single story clusters.
- **Story merge & enrichment** — adjacent `[Story]` entries collapse; optional synopsis enrichment with user consent.
- **Narrative chapter indexing** — restarts per comment block (1, 2, 3); omits sub-chapter header for single-chapter blocks.
- **Reference restructure** — split into `stream/`/`games/`/`tokusatsu/` subfolders; added uwufufu + FGO + anime-talk references.
- **Intro segment breakdown** — long openings split into 3–5-min sub-topic milestones.

### Changed
- Title cleaning — increased max_len, strips leading Thai vowels to prevent truncated titles.
- README restructured with clear quickstart + `npx skills` as recommended universal installer.

---

## [1.1.2] — 2026-07-23

### Changed
- **Skill Organization & Structure (Matt Pocock Pattern)** — reorganized sub-skills from 29 flat directories down to 16 entry-points. Sub-skills used strictly by orchestrators (`anibon-timestamper`, `creating-highlight-video`, `anibon-timestamper-local`) are now neatly housed in `references/` directories within their orchestrator skill folder.
- **Vision Verification Trigger Rules** — added explicit Vision inspection triggers (`ffmpeg` frame extraction + `view_file`) to `anibon-timestamper` and `anibon-talk-stream` for technical monologues, on-screen errors, and file container/codec discussions (e.g. WebM/AV1).
- **Complete Part Header Rules** — added strict rule enforcing concise, non-truncated section headers (`═══`) in generated timestamp Markdown outputs.

---

## [1.1.0] — 2026-07-16

### Added
- **`preparing-tools` skill** — pre-flight tool checker wired into all orchestrators; verifies `yt-dlp`, `ffmpeg`, `python3` are present before any skill runs.
- **Games reference index** (`docs/`) — lookup table mapping game names to canonical short-IDs used in timestamp tags.
- **Channel uploader names reference** (`docs/`) — curated list of verified Anibon channel names for transcript filtering.
- **Installation instructions via `npx skills`** — updated README with one-liner install path.

### Fixed
- **Image-verification gap** — subagents previously named games from transcript text alone. New `IMAGE FIRST` iron rule requires `view_file` on every chunk item with an `"image"` field before writing the description. Screen is now ground truth.
- **10-minute gap enforcement** — orchestrator checklist gains a mandatory gap-scan step after collecting subagent results and before final assembly. `NO GAPS` rule now explicitly requires verification both before and after assembly.
- **`assemble_timestamps.py` format drift** — script output now locked to the canonical `(⏱ เริ่ม: HH:MM:SS)` format defined in `summarizer-subagent-guide.md`. A `FORMAT LOCK` iron rule prevents future divergence; if tests pass but format differs, fix the script—not the spec.
- **`check_sections.py` WARN not treated as blocker** — orchestration checklist now states ⚠️ WARN or ❌ FAIL must be resolved before proceeding.
- **Unit tests re-synced** — `test_assemble_timestamps.py` assertions updated to match guide-canonical format.

### Changed
- **`subagent-prompt-template.md` Step 7** — expanded from one line to four explicit rules: load image, read screen UI, prohibit naming from transcript text alone, and describe rather than guess if image is unclear.
- **`summarizer-subagent-guide.md`** — separator block annotated as canonical spec with `FORMAT LOCK` notice.

---

## [1.0.0] — 2026-07-14

### Added
- Initial release: `anibon-timestamper`, `anibon-timestamper-local`, `anibon-timestamper-handoff` skills.
- `youtube-minutes-synthesis`, `livestream-scene-selection`, `highlight-*` family of skills.
- `cleaning-auto-transcripts`, `masking-royal-news`, `synthesizing-knowledge` skills.
- `building-reusable-cli-tools`, `writing-plugin-readme` skills.
- Core scripts: `prepare_video.py`, `assemble_timestamps.py`, `anibon-analyzer.py`, `check_sections.py`.
- FGO and YGO SQLite card databases with lookup scripts.
- Full test suite in `tests/`.
