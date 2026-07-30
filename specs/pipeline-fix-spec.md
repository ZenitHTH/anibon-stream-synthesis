# Pipeline Fix Spec

## Root Cause

`subagent-prompt-template.md` exists at `skills/anibon-timestamper/` but the
orchestrator **never loads it** when spawning subagents. Instead:

- Orchestrator writes ad-hoc prompts: "Process chunks 00-14 of a stream..."
- No OUTPUT CONTRACT section → subagents don't know 1-stamp default, 0 allowed
- No inline JSON → subagents can't read chunk data
- No density self-check → subagents output vague non-committal responses
- Orchestrator falls back to manual timestamp writing → loses domain depth
  from sub-skills (fgo-knowledge, talk-stream patterns, etc.)

## Fix Architecture

```
orchestrator
  ├── preflight-gate.py (BLOCKING) ← NEW
  │   ├── anibon-analyzer.py → gaps >10min?
  │   ├── detect_topics.py → sub-skill routing
  │   └── workspace integrity check
  │
  ├── subagent-prompt-builder.py (MANDATORY) ← NEW
  │   ├── loads subagent-prompt-template.md
  │   ├── injects chunk JSON inline
  │   ├── enforces OUTPUT CONTRACT (1-2 stamps, 0 allowed)
  │   ├── enforces density self-check
  │   └── produces 1 prompt per chunk (not batch)
  │
  ├── subagent N (1 chunk each)
  │
  └── assembly-gate.py ← NEW
      ├── deduplicate adjacent same-topic stamps
      ├── rewrite caveman headers (not auto-copied)
      ├── merge undersized parts (<4 stamps)
      ├── gap audit >15min
      └── byte limit check
```

## Key Changes

### 1. No Ad-Hoc Prompts

Before (broken):
```
Task: Process chunks 00-14 of an HSR stream...
```

After (fixed):
```
You are processing chunk_05.json (00:54:01 - 01:04:00).
CONTEXT: Stream recorded on 20260311 (~4 months ago).

## OUTPUT CONTRACT (read before anything else)
One chunk (600s) → 1 timestamp by default, 2 MAX. (0 is allowed!)
...
## TRANSCRIPT JSON
{...chunk data inline...}
```

### 2. 1 Chunk Per Subagent

Before: 1 subagent gets 15 chunks → shallow reading, 0-1 stamps total

After: 55 subagents × 1 chunk each → each reads its 600s window deeply

Caveat: For cloud context limits, batch into groups of 5-8 max, NOT 15+.

### 3. Pre-Flight Blocks Spawn

- `anibon-analyzer.py` must pass (no gaps >10min)
- `detect_topics.py` must classify routing
- Missing workspace files → abort

### 4. Assembly Enforces Quality

- Dedup: adjacent same-tag <10min apart → keep first, delete rest
- Headers: derive from full section content, not first stamp text
- Small parts (<4 stamps): merge into neighbor (unless byte cap prevents)
- Gaps >15min: flag for review
- Bytes: must pass check_sections.py

## Enforcement

The plugin adds these to the orchestrator's AGENTS.md or equivalent:

1. "subagent-prompt-builder.py MUST be used. Manual prompts forbidden."
2. "preflight-gate.py MUST pass before any subagent spawn."
3. "assembly-gate.py MUST pass before delivery."
4. "Violation = hard fail. Review and rerun."

## Files

| File | Purpose |
|------|---------|
| `scripts/subagent-prompt-builder.py` | Canonical prompt builder from template |
| `scripts/preflight-gate.py` | Pre-spawn checks |
| `scripts/assembly-gate.py` | Post-assembly validation |
| `plugin.json` | Plugin manifest |
| `specs/pipeline-fix-spec.md` | This document |
