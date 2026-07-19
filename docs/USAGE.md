# Usage Patterns

## Parallel Research (`synthesizing-knowledge`)

3+ sub-topics or 5+ searches → spawn parallel subagents. Prevents context bloat in main session.

## Hierarchical MapReduce (`anibon-timestamper`)

For streams > 2 hours:

1. **Split** into overlapping chunks (default 5-min, `--block 300 --overlap 30`)
2. **Parallel subagents** process each chunk with specialized sub-skills
3. **Reduce** — combine results, deduplicate, pack into byte-limited parts
4. **Verify** — run `check_sections.py` to validate YouTube comment sizes

### Local LLM Guardrails (Goldfish Brain Protocol)

Local models (gemma, qwen) have limited working memory and loop-prone behavior:

1. **ANTI-LOOP PROTOCOL** — stop generating and call a tool if detecting infinite reasoning ("Wait...", "Actually...")
2. **Explicit Path Resolution** — never reconstruct `[PLUGIN_ROOT]` from memory; use literal string deletion
3. **Zero-Padded Chunks** — filenames use `chunk_02.txt` not `chunk_2.txt` to prevent crash loops
4. **No Curiosity** — ban `ls`/`find`; blindly execute fallback commands instead of debugging paths
5. **Handoff** — invoke `anibon-timestamper-handoff` before context exhaustion

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
