# Usage Patterns

## Parallel Research (`synthesizing-knowledge`)

3+ sub-topics or 5+ searches → spawn parallel subagents. Prevents context bloat in main session.

## Hierarchical MapReduce (`anibon-timestamper`)

For streams > 2 hours:

1. **Split** into overlapping chunks (default 5-min, `--block 300 --overlap 30`)
2. **LiveChat & Mood Alignment** — extract livechat logs and run `analyze_555.py` to identify `MEME_PULSE` (555 laughter bursts) and emit per-chunk mood segments (`mood_555.json`)
3. **Parallel subagents** process each chunk/group (4–5 chunks each) with specialized sub-skills (`anibon-chunk-timestamper`), batched MAX 6 concurrent
4. **Full List Reveal Protocol** — subagents verify multi-item announcements across adjacent chunks before concluding total counts or character names
5. **Mood-Verified Descriptions** — `validate_mood.py` confirms mood-bearing timestamps honour each chunk's mood verdict
6. **Reduce** — combine results, deduplicate, audit gaps via `audit_gaps.py` (NO GAPS rule, max 10 min), pack into 5 byte-limited parts via `anibon-summarizer`
7. **Garbled-Word Feedback** — `anibon-garbled-notes` subagent consolidates `GARBLED_NOTES` blocks, writes `garbled_notes.json`, and appends confirmed rules to the shared `garbled_replacements.json` dictionary
8. **Verify** — run `check_sections.py` to validate YouTube comment sizes (target ≤ 3,500 bytes per section)

### Local LLM Guardrails (Goldfish Brain Protocol)

Local models (gemma, qwen) have limited working memory and loop-prone behavior:

1. **ANTI-LOOP PROTOCOL** — stop generating and call a tool if detecting infinite reasoning ("Wait...", "Actually...")
2. **Explicit Path Resolution** — never reconstruct `[PLUGIN_ROOT]` from memory; use literal string deletion
3. **Zero-Padded Chunks** — filenames use `chunk_02.txt` not `chunk_2.txt` to prevent crash loops
4. **No Curiosity** — ban `ls`/`find`; blindly execute fallback commands instead of debugging paths
5. **Handoff** — invoke `anibon-timestamper-handoff` before context exhaustion

### Story vs Talk Classification

Subagents classify Boat's activity:
- **`[Story]`** = Boat reads game/dialogue aloud. Consecutive `[Story]` entries merge into one.
- **`[Talk]`** = Boat analyzes/explains. Individual entries preserved.
- **Reference videos (JP VA no-commentary)** = pure story ground truth. Use aligned audio comparison to determine if commentary stream = Story or Talk.
- **Story Enrichment**: When `[Story]` source game/scene is identifiable, subagent asks user for permission to websearch synopsis → enriches timestamp with `(ref: game script)`.

### Thai Internet Subculture & Humor Rules

Subagents apply subculture psychology to avoid flattening streamer and chat banter:
- **Reverse Meaning / Playful Envy**: Fake anger ("กด dislike ละ") when streamer gets rare gacha = celebration & playful envy.
- **Ironic Cults / Overhype**: Hyping 1-star/2-star units ("Eric คือ META", "15 HP Clutch") = intentional meme banter $\rightarrow$ Verbs: `ฮาแซว`, `ปั่น`, `อวยมีม`.
- **Keyboard Typos & Slang**: Ingests `ถถถถ` (555 typos) and slang (`ทำถึง`, `จะ Crazy`, `อ่อม`, `ตึง`, `ตุย`, `สภาพ`).

### Final Assembly

`anibon-summarizer` subagent deduplicates cross-chunk overlaps, groups by activity period, and packs into byte-limited parts. `pack_timestamps.py` uses **greedy fill** (not DP partition) as the scripted fallback — produces minimum part count at byte_limit while preserving tag continuity within each part. Adjacent `[Story]` entries automatically merge.

### Garbled-Word Feedback Loop

Chunk subagents flag Thai-Latin hybrids that survived cleaning (`GARBLED_NOTES:` blocks, e.g. `"พีender" -> <correct|UNKNOWN> @ HH:MM:SS (chunk_NN)`). After merge, `anibon-garbled-notes`:
1. Consolidates + dedupes candidates across all chunk groups
2. Verifies each against the raw transcript context
3. Writes `garbled_notes.json` (`correct` or `null` for unresolved proper nouns)
4. Appends only HIGH-confidence rules to the shared `garbled_replacements.json`

The dictionary resolves via `resource_path()` up to plugin root, so every future stream auto-loads new rules. Ambiguous proper nouns stay `correct: null` for human confirmation — never guessed.

### Final Assembly (Windows)

```powershell
Get-Content -Encoding UTF8 chunk_*_output.md | Set-Content -Encoding UTF8 timestamp_VIDEO_ID.md
```

## Conditional Safety Masking (`masking-royal-news`)

Not applied by default. Only triggers on actual legal-risk signals:

| Trigger | Action |
|---------|--------|
| Boat names royal figure (ร.10, ราชินีสุทิดา, พระองค์ภา) | ✅ Mask |
| One Piece names used **off-lore** (connected to succession / ม.112) | ✅ Mask |
| Section 112 discussed in royal-specific context | ✅ Mask |
| General political party critique (ก้าวไกล, เพื่อไทย) | ❌ Skip |
| Election / civil policy commentary | ❌ Skip |
| Normal One Piece lore discussion | ❌ Skip |

**Quick test:** "ถ้าโพสต์ข้อความนี้ใน YouTube comment ตามตรง จะเสี่ยงต่อการฟ้องร้องตามมาตรา 112 ไหม?" — ถ้าไม่มี → ไม่ต้อง mask

---

# Iron Rules

1. **No hallucinated links** — every citation verified and active.
2. **Scratchpad before report** — write `bibliography_draft.md` with all URLs before final file.
3. **Parallel for broad topics** — 3+ sub-topics or 5+ searches → parallel subagents.
4. **Channel ownership** — not Anibon Official? Don't call speaker "Boat".
5. **Check runtimes first** — verify `python3`/`node` before running scripts.
6. **Ask on unknown terms** — phonetic mismatch → stop, show user, never guess.
7. **No ad-hoc scripts** — check `scripts/` first; write fallback only if file missing.
8. **Run `check_sections.py` after assembly** — never count YouTube chars manually.
9. **Anti-bot handling** — YouTube block → ask for browser cookie permission.
10. **Transcript required** — if unavailable, reject task; never guess timestamps.
11. **No hardcoded assembly** — always use `pack_timestamps.py` with flat timestamp list input.
12. **Story enrichment requires user consent** — never websearch for synopsis without asking.
13. **Full List Reveal Requirement** — never finalize list announcements (servants, banners) without reading across adjacent chunk boundaries.
14. **Greedy pack preserves tag continuity** — `pack_timestamps.py` fills to byte_limit, keeps same-tag clusters together.
15. **NO GAPS** — max 10 min between timestamps unless verified silent; run `audit_gaps.py` before summarizer.
16. **Use named agents** — chunk groups MUST use `anibon-chunk-timestamper`, garbled collection MUST use `anibon-garbled-notes`, assembly MUST use `anibon-summarizer`. Never substitute a generic Task/self agent.
17. **Subagent batching MAX 6** — never launch more than 6 concurrent subagents; process in batches.
18. **Don't guess garbled words** — unresolved proper nouns go to `garbled_notes.json` as `correct: null`, never appended as blind regex rules.
