# Local Pass 2 Accuracy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `anibon-timestamper-local` output with Gemma 4 12B close to the front-tier cleanup: 4–6 parts, ~40–60 essential stamps, and correct entity names.

**Architecture:** The probe (`brain/41bf292b.../scratch/probe_gemma.py`, stream `McgRhdbJXlU`) showed that Gemma 12B already prunes (44/47, 98% verbatim) and groups (4 parts) well. Name accuracy goes from 1/15 to 15/15 once a correct glossary is in the prompt. So the fixes go in the pipeline, not the model: (1) stop forced byte-cap splitting, (2) add one LLM pruning call before the part pass, with deterministic guards, (3) stop rule docs from filling `entity_glossary.json`.

**Tech Stack:** Python 3 stdlib, `unittest`, LM Studio OpenAI-compatible API (`anibon.lmstudio.call_local`).

**Spec:** This conversation's findings and probe results: `/Users/zenithth/.gemini/antigravity/brain/41bf292b-43fd-43b9-b653-85c3e5040cbc/scratch/probe_youtube_McgRhdbJXlU_workspace_gemma-4-12b-it-qat@q4_k_xl/result.json`

## Global Constraints

- Root: `skills/anibon-timestamper-local/` (git repo = `~/.gemini/config/plugins/anibon-stream-synthesis`). All paths below are relative to that root.
- Test command: `PYTHONPATH=scripts python3 -m unittest <module> -v` (no pytest installed).
- No new dependencies. No Pass 1 (`run_recursive_mode`) changes.
- `call_local` endpoint argument must be the full URL `.../v1/chat/completions`.
- Tags whitelist and timestamp line format `HH:MM:SS - [Tag] desc` unchanged.
- Fallback rule: any LLM failure → the previous deterministic behavior. The pipeline must never output fewer stamps because of an LLM error.

## Review Focus

1. Gemma rewrites stamp text while pruning → reject non-verbatim lines (Task 2 test `test_prune_drops_non_verbatim`).
2. Gemma returns garbage or very few lines → fall back to the full input list (Task 2 test `test_prune_falls_back_when_too_few`).
3. The prune drops the outro → always re-add the first stamp and any `[Ending]` stamp (Task 2 test `test_prune_keeps_first_and_ending`).
4. Short streams (≤60 stamps) get pruned needlessly → skip the call (Task 2 test `test_prune_skips_short_input`).
5. The real knowledge file `fgo-knowledge.md` in `references/stream/` gets dropped by the rule-doc filter → keep `*-knowledge.md` (Task 3 test `test_stream_knowledge_files_still_parsed`).

---

### Task 1: Byte cap opt-in only

**Files:**
- Modify: `scripts/anibon/summarizer.py:138` (`return enforce_byte_cap(...)` → `return "\n\n".join(rendered_parts)`)
- Modify: `scripts/process_chunks_local.py:275-298` (add `byte_cap: bool = False` param; line 298 runs only `if byte_cap:`), argparse near line 827 (add `--byte-cap`, `store_true`, help "Split parts >3500 bytes (single-comment mode)"), and pass `byte_cap=args.byte_cap` at the 3 call sites (≈565, 721, and wherever `no_summarizer_pass=args.no_summarizer_pass` is passed into finalize).
- Test: `tests/test_pipeline_e2e.py:104-124`, `tests/test_summarizer.py:20-32`

**Interfaces:**
- Produces: `finalize_and_assemble_timestamps(..., glossary=None, byte_cap: bool = False)`

- [x] **Step 1: Replace the cap test with two tests in `tests/test_pipeline_e2e.py`**

```python
def test_finalize_does_not_split_by_default(self):
    # same 30 stamps x 120 'ข' setup as before
    out_md, _ = finalize_and_assemble_timestamps(..., no_summarizer_pass=True)
    blocks = [b for b in out_md.read_text(encoding="utf-8").split("\n\n") if b.strip()]
    self.assertTrue(any(len(b.encode("utf-8")) > 3500 for b in blocks))

def test_finalize_byte_cap_opt_in(self):
    out_md, _ = finalize_and_assemble_timestamps(..., no_summarizer_pass=True, byte_cap=True)
    for b in out_md.read_text(encoding="utf-8").split("\n\n"):
        if b.strip():
            self.assertLessEqual(len(b.encode("utf-8")), 3500)
```

Remove the 3,500 assertion loop from `test_assemble_parts_borders_and_byte_limit`. Keep the other asserts. Rename it to `test_assemble_parts_borders`.

- [x] **Step 2: Run, expect FAIL** — `PYTHONPATH=scripts python3 -m unittest tests.test_pipeline_e2e -v` → `test_finalize_does_not_split_by_default` FAIL, `byte_cap` TypeError.
- [x] **Step 3: Implement** the edits listed under Files.
- [x] **Step 4: Run, expect PASS** — `PYTHONPATH=scripts python3 -m unittest tests.test_pipeline_e2e tests.test_summarizer -v`
- [x] **Step 5: Commit** — `git commit -am "fix(local): byte cap opt-in, stop forced micro-part split"`

---

### Task 2: LLM essential pruning before part pass

**Files:**
- Modify: `scripts/anibon/summarizer.py` (add `prune_essential`, put it before `run_local_summarizer_pass`)
- Modify: `scripts/process_chunks_local.py` `finalize_and_assemble_timestamps` (call it after `apply_vision_verify`, only when `not no_summarizer_pass`; then pass the pruned list to both `run_local_summarizer_pass` and `assemble_parts`; return the pruned list)
- Test: `tests/test_summarizer.py`

**Interfaces:**
- Consumes: `call_local(endpoint, model, prompt, max_tokens, temperature, timeout=...)`
- Produces: `prune_essential(endpoint: str, model: str, stamps: List[str], temperature: float = 0.1, min_input: int = 60) -> List[str]`

Rules (exact values):
- `len(stamps) <= min_input` → return `stamps` unchanged, no call.
- `target = max(40, min(60, len(stamps) // 4))`.
- Prompt = the T1 prompt from `probe_gemma.py` lines 26-31, with `{target}`. `max_tokens=4000`, `timeout=600`.
- Keep only reply lines that are **exact** members of `stamps`, deduplicated.
- If kept `< target // 2` or the call raises → return `stamps`.
- Always re-add `stamps[0]` and every line containing `[Ending]`. Return sorted by `parse_ts(line[:8])`.
- Print `[prune] {len(stamps)} -> {len(result)}`.

- [x] **Step 1: Write failing tests** (patch `anibon.summarizer.call_local` with `unittest.mock.patch`)

```python
STAMPS = [f"{i//60:02d}:{i%60:02d}:00 - [Talk] หัวข้อ {i}" for i in range(100)] + ["01:45:00 - [Ending] ปู่โบ๊ตขอบคุณผู้ชมและกล่าวปิดสตรีม"]

def test_prune_drops_non_verbatim(self):  # reply = 40 real lines + "00:05:00 - [Talk] แต่งเอง"
    self.assertNotIn("00:05:00 - [Talk] แต่งเอง", out); self.assertTrue(set(out) <= set(STAMPS))
def test_prune_falls_back_when_too_few(self):  # reply = 3 real lines
    self.assertEqual(out, STAMPS)
def test_prune_falls_back_on_error(self):  # side_effect=RuntimeError
    self.assertEqual(out, STAMPS)
def test_prune_keeps_first_and_ending(self):  # reply = 40 lines from STAMPS[10:50]
    self.assertIn(STAMPS[0], out); self.assertIn(STAMPS[-1], out); self.assertEqual(out, sorted(out, key=lambda l: parse_ts(l[:8])))
def test_prune_skips_short_input(self):  # 30 stamps
    mock.assert_not_called(); self.assertEqual(out, STAMPS[:30])
```

- [x] **Step 2: Run, expect FAIL** — `PYTHONPATH=scripts python3 -m unittest tests.test_summarizer -v` → ImportError `prune_essential`.
- [x] **Step 3: Implement** `prune_essential` and wire it into `finalize_and_assemble_timestamps`.
- [x] **Step 4: Run, expect PASS** — `PYTHONPATH=scripts python3 -m unittest tests.test_summarizer tests.test_pipeline_e2e -v` (e2e uses `no_summarizer_pass=True`, so no network).
- [x] **Step 5: Commit** — `git commit -am "feat(local): LLM essential pruning with verbatim guard before Pass 2"`

---

### Task 3: Keep rule docs out of entity glossary

**Files:**
- Modify: `scripts/anibon/knowledge_reader.py:211-222` (`extract_entity_glossary` loop)
- Test: `tests/test_knowledge_reader.py`

**Interfaces:**
- Produces: `is_rule_doc(path: Path) -> bool` in `knowledge_reader.py`. Returns True when `path.parent.name == "stream"` and `not path.stem.endswith("-knowledge")`. The loop does `continue` for rule docs.

- [x] **Step 1: Write failing tests** (tempdir with `stream/talk-stream.md` holding `- **Core Strategy**: x` and `| **Direct royal naming** | y | z |`, plus `stream/fgo-knowledge.md` holding `- **Ashiya Douman (อาชิยะ โดมัน)**: caster`; signals `{"0": {"best_file": "talk-stream.md", "weighted_files": ["fgo-knowledge.md"]}}`; `ref_dir=tmp/"stream"`)

```python
def test_rule_docs_excluded(self):
    self.assertNotIn("Core Strategy", g); self.assertNotIn("Direct royal naming", g)
def test_stream_knowledge_files_still_parsed(self):
    self.assertIn("Ashiya Douman", g)
```

- [x] **Step 2: Run, expect FAIL** — `PYTHONPATH=scripts python3 -m unittest tests.test_knowledge_reader -v` → `test_rule_docs_excluded` FAIL.
- [x] **Step 3: Implement** `is_rule_doc` and the `continue`.
- [x] **Step 4: Run, expect PASS** — `PYTHONPATH=scripts python3 -m unittest discover -s tests -v` (full suite, nothing else breaks).
- [x] **Step 5: Commit** — `git commit -am "fix(local): exclude stream rule docs from entity glossary"`

---

### Task 4: Live verification on real stream + SKILL.md sync

**Files:**
- Create: `/Users/zenithth/.gemini/antigravity/brain/41bf292b-43fd-43b9-b653-85c3e5040cbc/scratch/verify_pass2.py`
- Modify: `SKILL.md` (Quick Commands section 2: document `--byte-cap`; Essential Curated Timestamps section: say pruning is automatic via `prune_essential` for >60 stamps)

- [x] **Step 1: Write `verify_pass2.py`** — copy `~/youtube_McgRhdbJXlU_workspace/{all_timestamps.txt,signals.json}` into a tempdir, run `run_knowledge_discovery` (or `extract_entity_glossary` + `save_entity_glossary`), then `finalize_and_assemble_timestamps(endpoint="http://100.115.25.30:1234/v1/chat/completions", model="gemma-4-12b-it-qat@q4_k_xl", temperature=0.1, block_size=2400, no_summarizer_pass=False, glossary=g)`. Print: stamp count, part count, stamps per part, glossary key count, and any glossary keys from the stream rule docs.
- [x] **Step 2: Run** `python3 -X utf8 verify_pass2.py` (~10 min). **Pass =** 40–60 stamps, 4–6 parts, no part ≤2 stamps, an `[Ending]` stamp present, 0 rule-doc keys.
- [x] **Step 3: Update SKILL.md** with the two notes above.
- [x] **Step 4: Commit** — `git commit -am "docs(local): document --byte-cap and auto essential pruning"`
