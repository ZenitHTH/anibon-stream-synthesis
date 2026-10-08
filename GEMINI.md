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

When using `agy` for vision proxy, always use the newest model. Never pin to an older version like Gemini 3.5. Old models have context/quality limitations that cause failures. Current: `Gemini 3.6 Flash`.

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
   - All assembled comment blocks must strictly remain under the 3,500-byte target ceiling per YouTube comment.
