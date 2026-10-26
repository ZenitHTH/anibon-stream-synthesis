# Anibon Stream Synthesis — Global Rules

## Orchestrator Pipeline Guard

When executing any skill in this plugin that requires spawning parallel chunk subagents (`anibon-timestamper`, `creating-highlight-video`, `youtube-minutes-synthesis`):

**NEVER replace the subagent dispatch stage with an inline script or ad-hoc Python code.**

The full subagent pipeline must be followed exactly as documented in each skill's SKILL.md. Shortcutting produces shallow, generic, templated output and is a hard failure.

Symptoms of a violation:
- Writing `generate_timestamps.py` or any custom script that emits timestamps from chunks directly.
- Timestamps that repeat the same generic label across many time ranges (e.g., `[Talk] ตอบคำถามแชท` repeated 30+ times).
- Zero reference to specific characters, story beats, or game events that were actually discussed.

Correct behavior: After `preflight-gate.py` passes, the next step is **always** `invoke_subagent` per chunk using `subagent-prompt-template.md`.

## agy Model Rule

When using `agy` for vision proxy, always use the newest model. Never pin to an older version like Gemini 3.5. Old models have context/quality limitations that cause failures. Current: `Gemini 3.8 Flash (High)`.

## Streamer Identity & Local Anti-Hallucination Invariants

Whenever processing, generating, auditing, or summarizing timestamps for Anibon livestreams (especially via local models or `anibon-timestamper-local`):

1. **Streamer Identity Invariant**:
   - The streamer is exclusively **`ปู่โบ๊ต`** (Boat).
   - **NEVER** write or emit `ปู่บอท`, `ลุงบอท`, or `ปู่โบต`. All agents must scrub this at buffer ingestion and audit stages.

2. **Anti-Guessing & Phonetic Constraint**:
   - Local models must **NEVER** arbitrarily translate or guess English spellings for Thai phonetics.
   - If an entity is not verified in `entity_glossary.json` or `references/*.md`, describe the action in Thai or write phonetic Thai. Never invent novel English proper nouns.
   - Pokémon names must always follow the standard format: `ชื่อไทย (English Name)`.

3. **Caveman Timestamp Style Invariant (No Leading Streamer Prefixes)**:
   - **NEVER** start timestamp lines or section titles (`ส่วนที่ X`) with `'ปู่โบ๊ต'` (viewers already know who the streamer is).
   - **NEVER** repeat the same opening verb consecutively across lines (e.g. avoid repeating `'วิเคราะห์...'` or `'พูดถึง...'` line after line).
   - **Action-First & Topic-First Phrasing**: Use crisp Caveman style: `[กริยาหลากหลาย/ประเด็นหลัก] + [ชื่อเฉพาะ] + [ใจความสำคัญกระชับ]`.
   - Use varied first-verbs: `ส่อง`, `ชำแหละ`, `เทียบ`, `เจาะลึก`, `เม้าท์มอย`, `สรุปดราม่า`, `กางทฤษฎี`, `รีวิว`, `พักเบรก`, `ปิดไลฟ์`, or begin directly with the subject/game title.
   - Preserve 100% of verified proper nouns (games, characters, people).

4. **Stream Ending / Outro Guarantee**:
   - Never let continuous gameplay swallow the stream outro.
   - The final 5 minutes of transcript must always be inspected for closing tokens (`ขอบคุณครับ`, `ลงไลฟ์`, `ราตรีสวัสดิ์`, `บ๊ายบาย`) to emit `HH:MM:SS - [Ending] ปู่โบ๊ตขอบคุณผู้ชมและกล่าวปิดสตรีม`.

5. **Deterministic Multi-Layer Verification**:
   - Always execute the 4-layer defense pipeline: (1) Metadata ingestion, (2) Pre-inference buffer scrubbing, (3) Invariant prompt directives, (4) Stage 5 deterministic auto-sanitization against `garbled_replacements.json`.

6. **Macro-Thematic Cohesion & Essential Curation Invariant**:
   - **Section Splitting Invariant (Timestamp Line Count Over Byte Cap)**:
     - **Cancel Byte-Based Splitting**: NEVER evaluate or split macro-parts (`ส่วนที่ X`) using byte counts (e.g. 3,500B / 4,500B). UTF-8 byte counting unfairly penalizes Thai characters (3 bytes/char) and distorts section balance.
     - **Split by Timestamp Line Count**:
       - **Recommended Target**: ~15–20 timestamps per part.
       - **Soft Warning (`WARN`)**: > 20 timestamps in a single part.
       - **Hard Limit (`OVER` / Split Requirement)**: > 25 timestamps in a single part. If a part exceeds 25 timestamps, split it into two cohesive thematic sub-parts.
     - **Boundary Snapping**: When splitting an oversized part, snap to the nearest topic transition marker or line midpoint (`len(stamps) // 2`), NOT byte midpoint.
   - **Essential Timestamps Curation**: Prioritize high-impact, essential timestamps (~40–60 stamps for a 7–8 hour stream) as the primary user-facing output. Filter out conversational micro-loops, repetitive affirmations, and minor tangents while preserving major topic pivots, verified news, in-depth analysis, visual/gameplay highlights, and the stream outro. Keep the exhaustive chronological log in `all_timestamps.txt` / `anibon_timestamps_full.md` for ground-truth reference.
   - **Topic-Cluster Wrapping (Anti-Micro-Stamping)**: When adjacent timestamps discuss the same subject, wrap them into ONE unified timestamp. Never emit chains of micro-timestamps every 1–2 minutes for the same ongoing topic.
   - **Fleeting Side-Track Skipping**: Skip brief offhand comments spanning only a few sentences (<30–60s) with no substantive analysis (e.g. praising a Thai localization name, reading an off-screen chat joke, or momentary passing remarks).

7. **Canonical Version Chronology & Comparative Callback Guard**:
   - **Cross-Reference Version Tables**: When labeling live-service game updates (e.g. 7.2, 3.x), strictly cross-check the version chronology in `skills/anibon-world-identity/references/<Game>.md` to identify the official region/nation (e.g., 7.x = Snezhnaya, 6.x = Nod-Krai).
   - **Active Showcase vs. Comparative Callback**: The active stream showcase defines the section title and character affiliations. Never allow a streamer's nostalgic or comparative reference to an earlier version (e.g. "ตั้งแต่ตอนหนองคาย...") to overwrite the current update's canonical setting.
   - **Explicit Callback Phrasing**: Retrospective discussions must be framed as callbacks (e.g. `...พร้อมย้อนคุยเมต้าตัวละครตั้งแต่ยุค <Region> (<RegionEN>)`), never as the active version setting.

## Knowledge Maintenance & Dictionary Invariants

Whenever updating phonetic replacements or expanding domain knowledge in this plugin:

1. **Dictionary Schema Preservation (Schema v2)**:
   - **NEVER** perform raw `dict.update()` or write flat key-value pairs directly to `garbled_replacements.json`.
   - `garbled_replacements.json` strictly follows Schema v2:
     ```json
     {
       "version": 2,
       "mappings": {
         "CanonicalTarget": ["noise_pattern_1", "noise_pattern_2"]
       }
     }
     ```
   - **ALWAYS** update dictionary entries via the canonical CLI tool:
     ```bash
     python3 skills/cleaning-auto-transcripts/scripts/update_garbled_dictionary.py \
         --add "<CanonicalTarget>" "<noise_pattern_1>" "<noise_pattern_2>"
     ```
   - This ensures automatic normalization, regex safety checks, deduplication, and atomic updates to the single root resource (`resources/garbled_replacements.json`).

2. **Domain Knowledge File Lifecycle (`anibon-world-identity` & `anibon-live-service-researcher`)**:
   - When a livestream covers a major franchise or live-service game lacking a reference file or missing recent patches in `skills/anibon-world-identity/references/`, invoke **`anibon-live-service-researcher`** (checks real-time date via `time.is`, finds current + next version, recursively traces back ≥3 versions, and documents oldest-to-latest changes, updates, gacha banners, and story). Do not leave `signals.json` with 0 glossary matches.
   - Scaffold `references/<Franchise>.md` using standard markdown tables or bold bullets recognizable by `anibon/knowledge_reader.py`:
     - Format A (Table): `| English Name (Thai Name) | Role/Faction | Attribute/Note |`
     - Format B (Bullets): `- **Name (English / Thai)**: Description`
   - Register the file in `skills/anibon-world-identity/references/INDEX.md`.

3. **Pre-Flight Domain Knowledge Verification**:
   - Before launching chunk inference, check if video metadata (title, description) references an unindexed major franchise or game.
   - If `signals.json` yields 0 glossary entries for a title with obvious major franchise entities, scaffold the reference file (`references/<Franchise>.md`) and register in `INDEX.md` *prior* to starting chunk processing.
   - Never proceed into full inference with an empty glossary when domain entities are explicitly named in the stream title.

4. **Prohibition on Ad-Hoc Dataset Mutation**:
   - Always locate and use repository tools (`update_garbled_dictionary.py`, `fetch_*_db.py`) instead of writing raw Python scripts that append to JSON files.

5. **Garbled Collector Regex Safety & Grounding Invariants**:
   - **Substring Collision Prevention**:
     - **NEVER** add pure-ASCII noise patterns shorter than 5 characters (e.g. `"ON"`, `"anp"`, `"MDB"`) without strict word boundaries, as global regex replacement corrupts normal English words (e.g. `"Donghua"` → `"DNexonghua"`).
     - **NEVER** add a noise pattern if `garbled.lower() in target.lower()` (e.g. `"on"` in `"Nexon"`, `"Blue"` in `"Blue Archive"`).
     - **NEVER** add pure-Thai tokens without non-Thai script characters unless explicitly verified multi-syllable proper nouns, preventing common syllables (`บีด`, `เวฟ`) from corrupting normal Thai words (`ไมโครเวฟ`, `ทำครัว`).
   - **Strict Target Grounding (Zero Novel English Guesses)**:
     - Local LLMs must NEVER invent novel English proper nouns.
     - A canonical target is strictly rejected unless it exists in canonical dictionary keys (`garbled_replacements.json`), `entity_glossary.json`, stream title, OR verbatim in `whisper_segment`.
   - **Acoustic Alignment Step Requirement**:
     - Local pipelines must execute `resolve_garbled_notes` using acoustic segments from `whisper.cpp` and local LLM alignment before calling `update_garbled_dictionary.py`.
   - **Multi-Format Chunk Support**:
     - Chunk cleaners (`clean_garbled_english.py`) must support `.txt` chunks in addition to `.json` and `.xml`.



