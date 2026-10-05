---
name: anibon-search
description: Search the ANIBON livestream archive for topics, games, news, or moments Boat discussed. Use when the user asks "ค้นหา พูดถึงเกี่ยวกับ...", "ปู่โบ๊ตเคยพูดเรื่อง... ในสตรีมไหน", "หาคลิปที่ปู่โบ๊ตวิจารณ์...", or similar archive search queries.
---

# ANIBON Search Skill

## 1. Overview & Principles

### Purpose

This skill retrieves specific moments from the **ANIBON livestream archive** — a corpus of timestamped markdown files and compressed transcripts covering Boat's (ปู่โบ๊ต) livestreams. It answers questions like *"Which stream did Boat talk about X?"* or *"Find the clip where Boat criticized Y."*

### Hybrid Retrieval Architecture

The search pipeline is **deterministic** and uses no LLM at retrieval time:

| Stage | Mechanism |
|---|---|
| Lexical / Fuzzy | SQLite **FTS5 trigram** index over tokenised terms (Thai + Latin). Handles partial matches, common misspellings, and CJK/Thai substring queries. |
| Semantic | Pre-computed **vector embeddings** (sentence-level) compared via cosine similarity against the query's `semantic` field. |
| Fusion | **Reciprocal Rank Fusion (RRF)** combines lexical and semantic rank lists into a single ordered result set. |
| Moment Collapse | Results are collapsed to **600-second windows** so that multiple hits within the same 10-minute segment return as one moment entry rather than duplicate rows. |

### Source of Truth

All data lives under `timestamp_workspace/`:

- **Timestamp markdown files** — `by_video_id/*.md`
  - One file per video, containing section headers with `[HH:MM:SS]` anchors, topic labels, and short summaries.
- **Transcripts** — `transcripts/*.jsonl.gz`
  - Gzip-compressed JSON Lines; each line is a timestamped utterance (`{"t": "00:12:34", "text": "...", ...}`).

The CLI tool reads from these directories only. No external API, no live YouTube access.

### CLI Tool

```bash
python3 -m anibon_search search '<query_json>'
```

- **Working directory:** `/Users/zenithth/timestamp_workspace` (must be the CWD when invoking).
- **Input:** A single JSON string passed as one shell argument.
- **Output:** A JSON object on stdout containing `results[]`, `coverage{}`, and diagnostic fields.
- **No LLM calls.** The tool is purely deterministic: index lookups, vector dot-products, RRF math, and window collapse.

### Split of Labour

| Role | Responsibility |
|---|---|
| **AI (this skill)** | Interprets the user's natural-language query → builds the Query Contract JSON; inspects returned moments; filters false positives; formats the final answer for the user. |
| **`search.py`** | Executes FTS5 + vector retrieval, RRF fusion, 600 s collapse, and returns raw candidate moments with `matched_by` provenance. Makes no editorial or semantic judgement. |

---

## 2. Query Contract (JSON)

Every search call passes a single JSON object to the CLI. The schema is:

```json
{
  "terms": ["..."],
  "semantic": "...",
  "tags": ["Talk"],
  "date": { "from": "YYYY-MM-DD", "to": "YYYY-MM-DD" },
  "limit": 20
}
```

### Field Reference

| Field | Type | Required | Notes |
|---|---|---|---|
| `terms` | `string[]` | Yes (≥ 1) | Proper-noun variants: Thai/English spellings, acronyms, common misspellings. Fed to FTS5 trigram index. |
| `semantic` | `string` | Recommended | Free-text intent phrase for the vector embedding path. May include intent words (วิจารณ์, ดราม่า, สรุป). |
| `tags` | `string[]` | No | Section-level tags from the markdown front-matter (e.g. `"Talk"`, `"Gameplay"`, `"News"`). Applied as a **soft score boost (+0.005)** per matching tag; never a hard filter. |
| `date` | `{from, to}` | No | Inclusive date range (`YYYY-MM-DD`). Also a **soft score boost**, not a hard filter. Results outside the range are still returned but ranked lower. |
| `limit` | `int` | No (default 20) | Maximum number of collapsed moments to return. |

### Term Construction Rules

- **Include** proper-noun variants: Thai and English spellings, acronyms, well-known misspellings.
  - Example: `"WuWa"`, `"Wuthering Waves"` are both valid `terms` for the same game.
- **Exclude** intent / action words from `terms`. Words like `วิจารณ์`, `ดราม่า`, `สรุป`, `พูดถึง`, `เกี่ยวกับ` belong in `semantic` or `tags`, **not** in `terms`. Placing them in `terms` pollutes the trigram index and degrades precision.

### Tags & Date: Soft Boosts, Not Hard Filters

- A matching tag adds **+0.005** to the fused RRF score for that moment.
- A date within range adds a similar small boost.
- Neither field removes results from the candidate set. This ensures recall is preserved even when the user's date or tag guess is slightly off.

### Example Queries (Verbatim)

**Example 1 — Thai topic search**

User asks: *"ค้นหา พูดถึงเกี่ยวกับ เนเน่ นายแน่มาก"*

```json
{"terms": ["เนเน่", "นายแน่มาก"], "semantic": "เนเน่ นายแน่มาก"}
```

> `เนเน่` and `นายแน่มาก` are proper nouns (character / person names). No intent words needed; the semantic phrase mirrors the terms for vector coverage.

**Example 2 — Game review search with tag hint**

User asks: *"ค้นหาปู่โบ๊ตวิจารณ์ Wuwa"*

```json
{"terms": ["WuWa", "Wuthering Waves"], "tags": ["Talk"], "semantic": "วิจารณ์ Wuwa Wuthering Waves"}
```

> `WuWa` and its full name `Wuthering Waves` are both proper-noun variants. The intent word `วิจารณ์` lives in `semantic`. `"Talk"` is a soft tag boost for talk-style segments (as opposed to pure gameplay).

---

## 3. Step-by-Step Workflow

### Step 1 — Query Formulation

1. Parse the user's natural-language request (Thai, English, or mixed).
2. Identify **proper nouns** → populate `terms[]` with all known variants (Thai/English, acronyms, common misspellings).
3. Extract **intent / action words** (วิจารณ์, ดราม่า, สรุป, พูดถึง, เกี่ยวกับ) → place them in the `semantic` string only.
4. If the user mentions a segment type (talk, gameplay, news) or an approximate date window, add to `tags[]` and/or `date{}` as soft boosts.
5. Set `limit` (default 20; raise to 30–50 for broad exploratory queries).
6. Produce the final Query Contract JSON.

### Step 2 — Retrieval Execution

Run from `/Users/zenithth/timestamp_workspace`:

```bash
python3 -m anibon_search search '<query_json>'
```

- The `<query_json>` is the single-quoted JSON string from Step 1.
- Capture stdout as a JSON object. Expected top-level keys: `results`, `coverage`, and optional diagnostics (`elapsed_ms`, `fts_hits`, `vec_hits`).
- If the command errors (non-zero exit), check that CWD is correct and the JSON is valid (no trailing commas, proper escaping of Thai characters in shell).

### Step 3 — Result Verification & Filtering

For each entry in `results[]`:

1. **Inspect the moment:** review the returned section title, timestamp (`t`), video ID, and the `matched_by` field (e.g. `"fts"`, `"vector"`, `"both"`).
2. **Cross-check context:** open or recall the surrounding transcript / markdown section to confirm the topic actually matches the user's intent.
3. **Filter false positives:** discard moments where:
   - The proper noun appears only in passing (e.g. a 1-second mention inside an unrelated segment).
   - The `matched_by` is vector-only and the cosine score is low (< 0.75) with no lexical corroboration.
   - The section title or transcript content clearly contradicts the query intent.
4. **Rank survivors** by a combination of RRF score, `matched_by` provenance (prefer `"both"`), and contextual relevance you judge from the snippet.

### Step 4 — Iterative Refinement (Up to 3 Rounds)

If Step 3 yields zero or insufficiently relevant moments:

| Round | Action |
|---|---|
| **1** | Expand `terms[]` with discovered alternate names, game titles, character aliases, or transliterations found in the first-pass results' metadata. Re-run. |
| **2** | Broaden or adjust `semantic` (e.g. drop a restrictive intent word, add a synonym). Optionally widen `date{}` by ±7 days. Re-run. |
| **3** | Try a minimal contract: single most-specific proper noun in `terms`, short `semantic`. If still empty, proceed to Step 6. |

Do **not** exceed 3 refinement rounds. Each round must change at least one field of the Query Contract.

### Step 5 — Answer Presentation

For every verified moment, present:

- **Clickable YouTube timestamp link:**
  ```
  https://www.youtube.com/watch?v=VIDEO_ID&t=SECs
  ```
  where `SECs` is the integer total seconds from the start of the video (e.g. `01:23:45` → `5025`).
- **Video title** (from archive metadata).
- **Upload date** (`YYYY-MM-DD`).
- **Section title** (the markdown section header that contains the moment).
- **Why it matched:** one sentence explaining which term(s) / tag / semantic phrase triggered the hit and what Boat was discussing at that timestamp.

Format as a numbered or bulleted list. If multiple moments come from the same video, group them under one video heading with sub-bullets for each timestamp.

### Step 6 — Fallback & Abstain

If after up to 3 refinement rounds no relevant moment is found:

1. **Abstain.** Do not guess, extrapolate, or fabricate a timestamp.
2. State clearly that the archive does not contain a matching segment for the queried topic.
3. Report coverage from the `coverage` JSON field returned by the CLI so the user understands the search boundary:
   - `date_range`: earliest and latest video dates in the index.
   - `total_videos`: number of videos indexed.
   - `level2_transcripts`: count (or range) of transcripts at detail level 2 available for full-text search.
4. Suggest a narrower or alternative phrasing if appropriate, but do not invent results.

---

## 4. Safety & Iron Rules

### R1 — No Hallucinated Timestamps

- **Never** present a timestamp, video ID, or section title that is not directly returned by `search.py` in the current session.
- If you are uncertain whether a moment was actually in the results, re-run the query before citing it.
- Do not interpolate between two known timestamps to "estimate" when something else was said.

### R2 — Royal News Masking

- **Never** display raw transcript snippets that contain unmasked royal-news content (Thai royal family references, names, or events) in a public-facing answer.
- If a matched moment's transcript section touches on such material:
  - Cite the timestamp link and section title only.
  - Summarise neutrally without quoting the raw text.
  - Apply the `masking-royal-news` convention before including any verbatim snippet in the response.

### R3 — Deterministic Retrieval Only

- Do not call external LLM APIs, web search engines, or YouTube APIs as part of this skill. All evidence must come from the local `timestamp_workspace` index via `search.py`.
- The AI's role is interpretation and presentation; retrieval is always delegated to the CLI.

### R4 — CWD Discipline

- Always execute the CLI from `/Users/zenithth/timestamp_workspace`. Running from a different directory will cause index-not-found errors or silent empty results.

### R5 — Quote Fidelity

- When quoting transcript text (after masking per R2), preserve the original Thai/Latin script exactly. Do not paraphrase, translate, or "clean up" the speaker's words unless explicitly asked by the user.
