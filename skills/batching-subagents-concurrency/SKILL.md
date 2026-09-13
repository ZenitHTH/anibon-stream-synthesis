---
name: batching-subagents-concurrency
description: Use when spawning multiple parallel subagents to process large datasets, transcript chunks, or batch workloads without hitting API rate limits or falling back to heuristics
---

# Batching Subagents Concurrency

## Overview

When processing long-form tasks (e.g., analyzing 20+ transcript chunks across an 8-hour livestream), spawning all subagents simultaneously exhausts model API rate limits (`429 RESOURCE_EXHAUSTED`). Batching subagents into controlled groups of **4–6 subagents** (max 8 for small prompts, `Model: "flash"`) per invocation turn guarantees continuous execution without rolling token-per-minute (TPM) quota exhaustion or fallback hallucinations.

## When to Use

- Launching 6 or more parallel subagents for chunk analysis, web scraping, or file processing.
- Experiencing `RESOURCE_EXHAUSTED` (429) rate limit errors during subagent invocation.
- Processing long livestreams or large multi-file repositories using `anibon-chunk-timestamper`.

**When NOT to use:**
- Running 1–5 independent subagents (can be launched directly in a single turn).

---

## Core Recipe (Batching Pattern)

### 1. Controlled Batch Size: 4–6 Subagents Per Turn (`Model: "flash"`)
For heavy tasks where each subagent receives large prompts (~50–100KB group manifests + transcript files), launch in batches of **4–6 subagents** (absolute max 8). Never launch 10+ subagents when prompts are heavy, as rolling token-per-minute (TPM) quotas will be exceeded.

```python
# ✅ GOOD: Controlled batch of 4–6 subagents with Flash tier
invoke_subagent(
    Subagents=[
        {"TypeName": "anibon-chunk-timestamper", "Role": "Group 00", "Model": "flash", "Prompt": "..."},
        {"TypeName": "anibon-chunk-timestamper", "Role": "Group 01", "Model": "flash", "Prompt": "..."},
        {"TypeName": "anibon-chunk-timestamper", "Role": "Group 02", "Model": "flash", "Prompt": "..."},
        {"TypeName": "anibon-chunk-timestamper", "Role": "Group 03", "Model": "flash", "Prompt": "..."}
    ]
)
# Stop calling tools. Wait for Batch 1 messages before launching Batch 2.
```

```python
# ❌ BAD: Spawning 10+ heavy-context subagents in a single turn
invoke_subagent(Subagents=[... 15 subagent specs ...]) # Triggers API 429 RESOURCE_EXHAUSTED
```

### 2. Explicit Model Tier Selection (`Model: "flash"`)
For high-volume data-reading and chunk-stamping subagents, explicitly pass `Model: "flash"` to utilize lighter model quotas and achieve 3x faster processing times.

### 3. Partial Batch 429 Recovery Recipe
If an API 429 occurs mid-batch during parallel execution:
1. **Audit Completed Outputs**: Check incoming messages and saved `chunk_*.txt` files to see which subagents delivered valid results before erroring. Subagents that finished their thinking often deliver their payload right as the error triggers.
2. **Never Re-run Succeeded Groups**: Retain all completed group outputs.
3. **Re-spawn Failed Groups in Micro-Batches**: Re-launch ONLY the missing/failed groups in a micro-batch of **2–3 subagents** with `Model: "flash"`. Do not re-run the entire batch.

---

## Anti-Hallucination Guardrail (No Heuristic Fallbacks)

> **NEVER SUBSTITUTE FAILING SUBAGENTS WITH HEURISTIC GENERATION SCRIPTS.**

If subagents fail or hit rate limits:
- ❌ **Do NOT** run regex or heuristic fallback scripts that synthesize fake or repetitive placeholder timestamps.
- ✅ **Do** kill lingering subagents (`manage_subagents(Action="kill_all")`), reduce batch size to 6-8, switch model tier to `"flash"`, and re-run subagents until 100% authentic outputs are produced from source data.

---

## Rationalization Table

| Excuse | Reality |
|---|---|
| "Spawning all 23 subagents at once is faster." | Triggers 429 rate limits, kills subagents, and wastes time retrying. |
| "If subagents fail, a heuristic Python script is a safe fallback." | Heuristics generate hallucinated, generic timestamps that break accuracy contracts. |
| "I don't need to specify `Model: 'flash'`." | Inheriting default heavy models burns API quota 5x faster. |

---

## Red Flags - STOP and Start Over

- Launching >10 subagents in a single tool call.
- Generating output using regex/heuristic text scripts when subagents fail.
- Continuing to call tools in a loop without waiting for active batch subagents to complete.
