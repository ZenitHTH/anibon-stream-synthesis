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
