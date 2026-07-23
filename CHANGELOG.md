# Changelog

All notable changes to **anibon-stream-synthesis** are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/). Versioning follows [Semantic Versioning](https://semver.org/).

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
