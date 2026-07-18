---
name: anibon-macro-density
description: Use when generating timestamps for any ANIBON stream and the output feels too long, has too many sections, or each 5-minute chunk produces its own timestamp. Load alongside anibon-timestamper to enforce macro-level density rules that keep output short while preserving all major context.
---

# Anibon Macro Density

Enforces aggressive timestamp merging so the final output stays compact (≤ 20 YouTube comments for a 9-hour stream) without losing any major context.

## The Problem This Skill Fixes

**Observed baseline failure (2026-07-18, stream Chdc68BJnNo):**
- 70 raw parts generated for a ~9-hour stream
- Most sections had 1 timestamp each
- Same ongoing talk topic got re-stamped every 5-minute chunk
- Result: verbose, spam-level comment quota usage

## Core Rule

**One timestamp = one MACRO activity shift, not one sub-topic mention.**

A 9-hour talk stream should produce ≤ 30 raw timestamps total.
After Summarizer merging → target 15–20 YouTube comments.

## Density Hierarchy

| What changed | Stamp? |
|---|---|
| Completely different game title | ✅ Yes |
| New guest speaker joins/leaves | ✅ Yes |
| Stream switches from gaming → talk (or vice versa) | ✅ Yes |
| Entirely new news story with no connection to prior topic | ✅ Yes |
| Sub-topic tangent within same ongoing conversation | ❌ No — fold into existing |
| Same topic continues across chunk boundary | ❌ No — output 0 timestamps |
| Minor donation read during ongoing talk | ❌ No — only stamp if it derails the topic 5+ min |
| Speaker mentions a new detail of the same story | ❌ No — update prior description |

## Merging Rules for Subagents

1. **Continuous talk = 1 stamp.** If Boat is still discussing the same news story, political topic, or game reaction across multiple chunks → that is 1 timestamp regardless of how many sub-angles he covers.
2. **0 is correct.** Outputting 0 timestamps for a chunk is the right answer when the chunk is a continuation. Do not feel pressure to produce output.
3. **Comma-list, not multi-line.** If two genuinely distinct topics occur in same chunk, fold them into one description: `วิเคราะห์ Prince Group, ติงช่องอมรินทร์ดราม่าเขมร` — one line.
4. **No sub-topic lines.** `[Talk] พูดถึง...` followed by another `[Talk]` 3 minutes later in same chunk = violation. Merge.

## Summarizer Density Rules

After Map stage collects all subagent results, the Summarizer MUST:

- Target **≤ 20 final parts** for streams up to 9 hours.
- Pack each part toward the 3,500-byte ceiling before splitting.
- Merge any two adjacent parts whose combined bytes stay under 3,200 — always.
- A final part with < 4 timestamps is a smell; merge it with its neighbor unless byte limit prevents it.

## Chunking Parameter Override

For next stream: use `--block 600 --overlap 60` (10-min chunks) instead of default `--block 300 --overlap 30`.
This halves the number of subagents and naturally enforces macro density.

## Red Flags — Output 0, Do Not Stamp

- Chunk starts with Boat still mid-sentence on prior topic.
- Only content is chat replies within an existing talk flow.
- Chunk is reaction to the same video/article already stamped in prior chunk.
- Donation that lasts < 2 minutes before returning to main topic.

## Real-World Impact

Without this skill: 70 parts, 70 YouTube comments needed.  
With this skill: ≤ 16 parts, 16 comments needed.  
Token cost and review time: roughly 4× cheaper.
