---
name: synthesizing-knowledge
description: Use when generating a comprehensive markdown knowledge document on a specific topic, where verified reference links and multi-source research are required.
---

# Synthesizing Knowledge

Deep-search a topic using web and video sources, then synthesize findings into a well-structured Markdown report with verified, accessible references.

## When to Use

- User wants a knowledge document, summary, or report on a specific topic
- Up-to-date or in-depth information not in model memory is needed
- Verified, clickable references are required for credibility
- **YouTube transcript / meeting minutes** → use `youtube-minutes-synthesis` instead

## Delegation Rule

3+ sub-topics **or** 5+ searches → dispatch parallel `research` subagents. Otherwise search directly.

Every subagent prompt **must** include: *"Provide the full URL to the specific article (e.g., https://example.com/articles/foo), NOT the domain homepage."*

**REQUIRED for subagent prompt structure:** Use parallel subagent dispatch (use whatever parallel mechanism the current tool supports).

## STRICT Process
**CRITICAL DIRECTIVE**: You are REQUIRED to follow this process strictly, step-by-step.
- You MUST execute ONE step at a time.
- DO NOT skip ahead under any circumstances.

1. **Environment Check** — check first if the OS is Linux, macOS, or Windows, and if the shell is Bash, Zsh, or PowerShell. Adapt all scripts and commands to match the environment. *(Run `echo $SHELL` and `uname -a` for Unix, or `$PSVersionTable` for Windows. Verify required tools exist via `command -v <tool>` for Unix or `Get-Command <tool>` for Windows).*
2. **Analyze** — identify main topic, sub-topics, search keywords
3. **Research** — search web + video; dispatch parallel subagents if threshold met
4. **Scratchpad** — write `<working_dir>/bibliography_draft.md` with all URLs and facts **before** the final report *(In Antigravity this is the `scratch/` dir; in Claude Code or OpenCode pick any session-scoped temp directory)*
5. **Verify URLs** — run resolve script; re-search any homepage-only results
6. **Synthesize** — write report using only scratchpad-defined indices; append `## References`

## URL Quality

| URL type | Action |
|---|---|
| Specific article path | ✅ Accept |
| Webcache / Smart redirect | ✅ Accept — run resolve script. It automatically extracts canonical URLs from `webcache` and `vertexaisearch` links and replaces them cleanly. |
| Homepage-only (`https://example.com`) | ❌ Re-search `site:example.com [keyword]`; after 2 failed attempts, annotate `[Homepage fallback]` |

**Never reconstruct or guess URL subpaths.**

## Resolve Script

Run **synchronously** (wait for the script to complete — mechanism depends on tool; allow at least links × 10 s, min 60 s):

```bash
python <skill_folder>/scripts/resolve_markdown_links.py <path-to-report.md>
```

Wait for `=== SCRIPT COMPLETE ===`. Act on any `[HOMEPAGE WARNING]` or `[BROKEN LINK WARNING]` before finalizing.

> ⚠️ Never run as a background task — the file will not be updated in time.

## Citation Rules

- Write bibliography first; use only those indices inline
- Never cite `[N]` where N > total entries in bibliography
- Reuse the same index for multiple facts from one source
- Every direct quote, statistic, or key fact needs an inline `[N]`
- **90% fidelity**: don't distort, exaggerate, or misrepresent sources

## Template

```markdown
# [Topic Title]

> **Summary**: [2–3 sentences]
> **Last Updated**: [date]

## 1. Overview
[High-level intro]

## 2. [Sub-topic]
[Details with citations, e.g. "78% of users prefer dark mode [1]."]

## References

### Websites & Articles
- [1] [Article Name](URL) — brief description

### Videos & Media
- [2] [Video Title](YouTube URL) — brief description
```

## Common Mistakes

| Mistake | Fix |
|---|---|
| Hallucinated links | Only use URLs returned by actual search results. Never guess or fabricate links. |
| Guessing Canonical URLs | If you get a `webcache` or `vertexaisearch` link, **do not try to guess** the real link. Provide the exact cache link you found and let `resolve_markdown_links.py` extract it safely. |
| Homepage citations | Find the specific article URL or use smart redirect. Homepage = last resort. |
| 5+ sequential searches in parent | Delegate to parallel subagents. Don't search sequentially yourself. |
| Skipping scratchpad | Write `bibliography_draft.md` before the report. Every time. |
| Out-of-range `[N]` | Finalize bibliography first; never cite an index you haven't defined. |
| Mixed languages | Headings, body, and references must all be one consistent language. |
| Resolve script in background | Always synchronous. Wait for `=== SCRIPT COMPLETE ===`. |

## Iron Rules

- **No report before scratchpad.** The file write tool (`write_to_file` in Antigravity, `Write` in Claude Code, native file write in OpenCode) for the final report is forbidden until bibliography draft is saved.
- **No homepage citations without annotation.** Annotate `[Homepage fallback]` if no article URL found after two searches.
- **No background resolve script.** Always synchronous — wait for `=== SCRIPT COMPLETE ===` before proceeding (mechanism depends on tool).
