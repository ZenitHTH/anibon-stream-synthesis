import os
import json
import glob
import re
import sys
import argparse

def build_prompts(workspace):
    chunks_dir = os.path.join(workspace, "chunks")
    signals_file = os.path.join(workspace, "signals.json")
    livechat_dir = os.path.join(workspace, "livechat")
    activity_dir = os.path.join(workspace, "activity")
    mood_file = os.path.join(workspace, "mood_555.json")
    prompts_dir = os.path.join(workspace, "prompts")
    by_chunk_dir = os.path.join(workspace, "prompts_by_chunk")
    os.makedirs(prompts_dir, exist_ok=True)
    os.makedirs(by_chunk_dir, exist_ok=True)

    with open(signals_file, 'r', encoding='utf-8') as f:
        signals_data = json.load(f)

    mood_data = {}
    if os.path.exists(mood_file):
        with open(mood_file, 'r', encoding='utf-8') as f:
            mood_data = json.load(f)

    # signals_data can be a list or dict
    if isinstance(signals_data, list):
        signals_map = {item["chunk_id"]: item for item in signals_data}
    else:
        signals_map = signals_data.get("chunks", signals_data)

    chunk_files = sorted(glob.glob(os.path.join(chunks_dir, "chunk_*.xml")))
    
    # Extract chunk numbers
    chunk_items = []
    for cf in chunk_files:
        base = os.path.basename(cf)
        m = re.search(r'chunk_(\d+)', base)
        if m:
            cnum = int(m.group(1))
            chunk_items.append((cnum, cf, f"chunk_{m.group(1)}"))

    chunk_items.sort(key=lambda x: x[0])

    # 1. Generate individual chunk files in prompts_by_chunk/ (safe for view_file <46KB limit)
    for cnum, cpath, cid in chunk_items:
        csig = signals_map.get(cid, {})
        primary_topic = csig.get("primary_topic", "unknown")
        best_file = csig.get("best_file", "none")
        conf = csig.get("confidence", 0.0)

        # Livechat
        lc_path = os.path.join(livechat_dir, f"livechat_{cid}.txt")
        lc_content = "no livechat available"
        if os.path.exists(lc_path):
            with open(lc_path, 'r', encoding='utf-8') as lcf:
                lc_content = lcf.read()

        # Activity
        act_path = os.path.join(activity_dir, f"activity_{cid}.txt")
        act_content = "no visual activity data"
        if os.path.exists(act_path):
            with open(act_path, 'r', encoding='utf-8') as act_f:
                act_content = act_f.read().strip()

        # Mood
        cmood = mood_data.get(cid, {})
        mood_str = f"verdict: {cmood.get('verdict')}, tone: {cmood.get('tone')}, verbs: {cmood.get('verbs')}" if cmood else "no mood_555"

        try:
            import xml.etree.ElementTree as ET
            root = ET.parse(cpath).getroot()
            lines = []
            for el in root.findall("item"):
                ts = el.attrib.get("timestamp", "00:00:00")
                txt = (el.text or "").strip()
                if txt:
                    lines.append(f"{ts} | {txt}")
            chunk_dialogue = "\n".join(lines)
        except Exception:
            with open(cpath, 'r', encoding='utf-8') as cf:
                chunk_dialogue = cf.read()

        chunk_prompt_content = f"""=== {cid.upper()} ===
PRIMARY TOPIC: {primary_topic}
BEST KNOWLEDGE FILE: {best_file} (confidence: {conf})
MOOD & TONE GUIDANCE: {mood_str}
ON-SCREEN ACTIVITY: {act_content}

DETECTION SIGNALS:
{json.dumps(csig, ensure_ascii=False, indent=2)}

LIVE-CHAT LOG:
{lc_content}

TRANSCRIPT DIALOGUE:
{chunk_dialogue}
"""
        with open(os.path.join(by_chunk_dir, f"{cid}.txt"), 'w', encoding='utf-8') as bcf:
            bcf.write(chunk_prompt_content)

    # 2. Group by 5
    groups = []
    group_size = 5
    for i in range(0, len(chunk_items), group_size):
        groups.append(chunk_items[i:i+group_size])

    prev_topic = "Stream Intro / Chatting"
    for g_idx, group in enumerate(groups):
        group_prompt = []
        group_prompt.append(f"# Subagent Task: Process Group {g_idx + 1}/{len(groups)} (Chunks {group[0][0]} to {group[-1][0]})\n")
        group_prompt.append(f"PREVIOUS GROUP LAST TOPIC: {prev_topic}\n")
        group_prompt.append("CHUNK PROMPT FILES TO READ SEQUENTIALLY:")
        for cnum, cpath, cid in group:
            chunk_file_path = os.path.join(by_chunk_dir, f"{cid}.txt")
            group_prompt.append(f"- {cid}: file://{chunk_file_path}")
        group_prompt.append("\n" + "="*50 + "\n")

        for cnum, cpath, cid in group:
            csig = signals_map.get(cid, {})
            primary_topic = csig.get("primary_topic", "unknown")
            prev_topic = primary_topic

            chunk_by_path = os.path.join(by_chunk_dir, f"{cid}.txt")
            if os.path.exists(chunk_by_path):
                with open(chunk_by_path, 'r', encoding='utf-8') as cf:
                    group_prompt.append(cf.read())
                    group_prompt.append("\n" + "-"*40 + "\n")

        out_path = os.path.join(prompts_dir, f"group_{g_idx+1:02d}.txt")
        with open(out_path, 'w', encoding='utf-8') as out_f:
            out_f.write("\n".join(group_prompt))

    print(f"Generated {len(chunk_items)} chunk prompt files in {by_chunk_dir}")
    print(f"Generated {len(groups)} group prompt files in {prompts_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build chunk and group prompts for anibon subagents.")
    parser.add_argument("workspace", nargs="?", default=None, help="Path to YouTube workspace directory")
    args = parser.parse_args()

    if not args.workspace:
        parser.print_help()
        sys.exit(1)

    build_prompts(args.workspace)
