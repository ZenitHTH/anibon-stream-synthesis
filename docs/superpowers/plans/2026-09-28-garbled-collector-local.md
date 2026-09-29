# Add Garbled Collector to anibon-timestamper-local Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the garbled collector / feedback loop (`whisper_dispatcher.py` + `update_garbled_dictionary.py`) into `anibon-timestamper-local` SKILL.md and documentation without over-engineering or modifying unnecessary code.

**Architecture:** Symlink `whisper_dispatcher.py` from `anibon-timestamper` to `anibon-timestamper-local/scripts/` (reusing existing code per ponytail principles), document Stage 2.5 / Step 4 garbled harvesting workflow in `anibon-timestamper-local/SKILL.md`, and verify execution paths.

**Tech Stack:** Bash / Python / Markdown / whisper.cpp

**Spec:** User request: "adding process of garbled collector" to `anibon-stream-synthesis/skills/anibon-timestamper-local`.

## Global Constraints

- Terse, minimal solution (ponytail + caveman). Re-use existing `whisper_dispatcher.py` and `update_garbled_dictionary.py`.
- No new dependencies or code rewrites where symlinking and documenting existing robust scripts suffices.
- Cross-platform documentation (macOS, Linux, Windows paths).

## Review Focus

1. Symlink correctness across relative paths (`../../anibon-timestamper/scripts/whisper_dispatcher.py`).
2. Verification that `whisper_dispatcher.py --help` runs without import errors from the local scripts directory.
3. Accurate pipeline table and quick commands in `anibon-timestamper-local/SKILL.md`.
4. Clear distinction between automated pre-normalization (Stage 0) and post-segmentation garbled harvesting & whisper ground-truth resolution.

---

### Task 1: Re-use whisper_dispatcher.py in anibon-timestamper-local scripts

**Files:**
- Create: `skills/anibon-timestamper-local/scripts/whisper_dispatcher.py` (symlink to `../../anibon-timestamper/scripts/whisper_dispatcher.py`)

**Interfaces:**
- Consumes: `skills/anibon-timestamper/scripts/whisper_dispatcher.py`
- Produces: CLI executable `skills/anibon-timestamper-local/scripts/whisper_dispatcher.py`

- [ ] **Step 1: Create symlink**

```bash
ln -sf ../../anibon-timestamper/scripts/whisper_dispatcher.py skills/anibon-timestamper-local/scripts/whisper_dispatcher.py
```

- [ ] **Step 2: Verify symlink and test invocation**

Run: `python3 skills/anibon-timestamper-local/scripts/whisper_dispatcher.py --help`
Expected: Help output displayed with exit code 0.

- [ ] **Step 3: Commit symlink**

```bash
git add skills/anibon-timestamper-local/scripts/whisper_dispatcher.py
git commit -m "feat(local): symlink whisper_dispatcher to anibon-timestamper-local"
```

---

### Task 2: Document Garbled Collector Process in anibon-timestamper-local SKILL.md

**Files:**
- Modify: `skills/anibon-timestamper-local/SKILL.md`

**Interfaces:**
- Documents:
  1. Pipeline Architecture Table: Stage 2.5 Garbled Harvesting & Whisper Ground Truth (`whisper_dispatcher.py` + `update_garbled_dictionary.py`).
  2. Quick Commands: Step 2.5 running `whisper_dispatcher.py` and updating dictionary.
  3. Ground-truth loop notes (P100 / Vulkan / Metal acceleration).

- [ ] **Step 1: Update SKILL.md with Stage 2.5 Garbled Collection**

Add Stage 2.5 to Pipeline Architecture table and add command instructions to Core Pipeline section in [SKILL.md](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper-local/SKILL.md).

- [ ] **Step 2: Validate SKILL.md formatting**

Inspect `skills/anibon-timestamper-local/SKILL.md` with `view_file` to ensure markdown tables and code fences are valid.

- [ ] **Step 3: Commit SKILL.md changes**

```bash
git add skills/anibon-timestamper-local/SKILL.md
git commit -m "docs(local): document garbled collector process in anibon-timestamper-local"
```
