"""
subagent-prompt-builder.py — Canonical prompt builder.

Root cause: orchestrator bypasses subagent-prompt-template.md, writes
ad-hoc prompts without OUTPUT CONTRACT. Subagents produce vague output.

Fix: This script loads template.md, injects chunk JSON, enforces contract.
Orchestrator MUST call this before every subagent spawn. No ad-hoc prompts.
"""

import json, sys, os
from datetime import datetime

def build_prompt(template_path, chunk_path, upload_date=None, time_ago=None,
                 sub_skill_rules=None, iron_rules=None):
    """
    Build canonical subagent prompt from template + chunk data.

    Args:
        template_path: path to subagent-prompt-template.md
        chunk_path: path to chunk JSON file
        upload_date: stream upload date string
        time_ago: relative time string (e.g. "~4 months ago")
        sub_skill_rules: list of iron rule strings from loaded sub-skills
        iron_rules: additional orchestrator iron rules

    Returns:
        dict with keys: prompt (str), chunk (parsed dict), metadata
    """
    with open(template_path, encoding='utf-8') as f:
        template = f.read()

    with open(chunk_path, encoding='utf-8') as f:
        chunk = json.load(f)

    items = chunk.get('items', [])
    chunk_id = os.path.splitext(os.path.basename(chunk_path))[0]

    # Determine chunk time range
    start_sec = items[0]['start'] if items else 0
    end_sec = items[-1]['start'] + items[-1]['duration'] if items else 0

    h1, m1, s1 = int(start_sec//3600), int((start_sec%3600)//60), int(start_sec%60)
    h2, m2, s2 = int(end_sec//3600), int((end_sec%3600)//60), int(end_sec%60)

    start_ts = f"{h1:02d}:{m1:02d}:{s1:02d}"
    end_ts = f"{h2:02d}:{m2:02d}:{s2:02d}"

    # Build prompt sections
    lines = []
    lines.append(f"You are processing {chunk_id} ({start_ts} - {end_ts}).")
    lines.append(f"CONTEXT: Stream recorded on {upload_date or 'unknown'} ({time_ago or 'unknown'}).")
    lines.append("")

    # Step 0: OUTPUT CONTRACT (must be first, per template)
    lines.append("## OUTPUT CONTRACT (read before anything else)")
    lines.append("")
    lines.append(f"One chunk ({int(end_sec-start_sec)}s) → **1 timestamp by default, 2 MAX. (0 is allowed!)**.")
    lines.append("A new timestamp is only valid when ONE of these occurs:")
    lines.append("- Game switches entirely (different title)")
    lines.append("- Speaker joins or leaves (Discord guest, etc.)")
    lines.append("- Completely different activity begins")
    lines.append("- A completely NEW topic of conversation begins")
    lines.append("")
    lines.append("**CRITICAL:** If this chunk is CONTINUING the exact same topic, story, or game activity")
    lines.append("from the previous chunk, you should output **0 timestamps**.")
    lines.append("")
    lines.append("Multiple sub-topics within one continuous talk → MERGE into 1 timestamp.")
    lines.append("If unsure → merge. Never split.")
    lines.append("")

    # Sub-skill rules
    if sub_skill_rules:
        lines.append("## SUB-SKILL IRON RULES")
        for rule in sub_skill_rules:
            lines.append(f"- {rule}")
        lines.append("")

    # Orchestrator iron rules
    if iron_rules:
        lines.append("## ORCHESTRATOR IRON RULES")
        for rule in iron_rules:
            lines.append(f"- {rule}")
        lines.append("")

    # Step 1-9 from template (condensed)
    lines.append("## Instructions")
    lines.append("1. Scan transcript. Identify PRIMARY activity.")
    lines.append("2. Use pre-calculated `timestamp` field from JSON. Do NOT calculate time.")
    lines.append("3. Select correct tag: [Greeting] [Talk] [News] [Chat] [Donation] [Gameplay] [Gacha] [Boss] [Death] [Victory] [WatchParty] [Reaction]")
    lines.append("4. Write description: max 10-12 words (~100 chars). Thai. One phrase.")
    lines.append("5. Format output: `HH:MM:SS - [Tag] Description`")
    lines.append("6. One line per timestamp. No headers, no intro, no explanation.")
    lines.append("")
    lines.append("## Density Self-Check (BEFORE submitting)")
    lines.append("Count your timestamps. If >2, merge until ≤2.")
    lines.append("Red flags → merge immediately or output 0:")
    lines.append("- Chunk starts mid-ongoing topic → Output 0")
    lines.append("- Two consecutive [Talk] stamps about same conversation → merge")
    lines.append("- Sub-topic shift within same game session → merge")
    lines.append("")

    # Inject JSON
    lines.append("## TRANSCRIPT JSON")
    lines.append(json.dumps(chunk, ensure_ascii=False, indent=2))
    lines.append("")

    prompt = "\n".join(lines)

    return {
        "prompt": prompt,
        "chunk_id": chunk_id,
        "start_ts": start_ts,
        "end_ts": end_ts,
        "num_items": len(items),
        "prompt_chars": len(prompt),
        "prompt_tokens_estimate": len(prompt) // 4
    }


def main():
    """CLI: python3 subagent-prompt-builder.py <template_path> <chunk_path> [--upload-date DATE] [--time-ago STR]"""
    if len(sys.argv) < 3:
        print("Usage: python3 subagent-prompt-builder.py <template.md> <chunk.json> [options]", file=sys.stderr)
        sys.exit(1)

    template_path = sys.argv[1]
    chunk_path = sys.argv[2]

    kwargs = {}
    for i in range(3, len(sys.argv)):
        if sys.argv[i] == "--upload-date" and i+1 < len(sys.argv):
            kwargs['upload_date'] = sys.argv[i+1]
        if sys.argv[i] == "--time-ago" and i+1 < len(sys.argv):
            kwargs['time_ago'] = sys.argv[i+1]

    result = build_prompt(template_path, chunk_path, **kwargs)
    print(result["prompt"])
    print(f"\n--- meta: {result['chunk_id']} {result['start_ts']}-{result['end_ts']} "
          f"{result['num_items']} items ~{result['prompt_tokens_estimate']}tokens ---",
          file=sys.stderr)


if __name__ == "__main__":
    main()
