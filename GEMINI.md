# Anibon Stream Synthesis — Global Rules

## Orchestrator Pipeline Guard

When executing any skill in this plugin that requires spawning parallel chunk subagents (`anibon-timestamper`, `creating-highlight-video`, `youtube-minutes-synthesis`):

**NEVER replace the subagent dispatch stage with an inline script or ad-hoc Python code.**

The full subagent pipeline must be followed exactly as documented in each skill's SKILL.md. Shortcutting produces shallow, generic, templated output and is a hard failure.

Symptoms of a violation:
- Writing `generate_timestamps.py` or any custom script that emits timestamps from chunks directly.
- Timestamps that repeat the same generic label across many time ranges (e.g., `[Talk] ตอบคำถามแชท` repeated 30+ times).
- Zero reference to specific characters, story beats, or game events that were actually discussed.

Correct behavior: After `anibon-analyzer.py` passes, the next step is **always** `invoke_subagent` per chunk using `subagent-prompt-template.md`.

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

3. **Stream Ending / Outro Guarantee**:
   - Never let continuous gameplay swallow the stream outro.
   - The final 5 minutes of transcript must always be inspected for closing tokens (`ขอบคุณครับ`, `ลงไลฟ์`, `ราตรีสวัสดิ์`, `บ๊ายบาย`) to emit `HH:MM:SS - [Ending] ปู่โบ๊ตขอบคุณผู้ชมและกล่าวปิดสตรีม`.

4. **Deterministic Multi-Layer Verification**:
   - Always execute the 4-layer defense pipeline: (1) Metadata ingestion, (2) Pre-inference buffer scrubbing, (3) Invariant prompt directives, (4) Stage 5 deterministic auto-sanitization against `garbled_replacements.json`.

5. **Macro-Thematic Cohesion & Essential Curation Invariant**:
   - **Drop 3,500-Byte Cap Over-Splitting**: Timestamps must be grouped strictly by cohesive macro-thematic activity periods (typically 4–6 parts for long streams). NEVER artificially slice a unified topic block into multiple sub-parts solely to satisfy a 3,500-byte comment ceiling. Single-comment byte limits are an optional export utility, not the structural grouping logic.
   - **Essential Timestamps Curation**: Prioritize high-impact, essential timestamps (~40–60 stamps for a 7–8 hour stream) as the primary user-facing output. Filter out conversational micro-loops, repetitive affirmations, and minor tangents while preserving major topic pivots, verified news, in-depth analysis, visual/gameplay highlights, and the stream outro. Keep the exhaustive chronological log in `all_timestamps.txt` / `anibon_timestamps_full.md` for ground-truth reference.

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
   - This ensures automatic normalization, regex safety checks, deduplication, and synchronization across both mirror copies (`resources/` and `skills/anibon-timestamper/resources/`).

2. **Domain Knowledge File Lifecycle (`anibon-world-identity`)**:
   - When a livestream covers a major franchise or topic lacking a reference file in `skills/anibon-world-identity/references/`, do not leave `signals.json` with 0 glossary matches.
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



