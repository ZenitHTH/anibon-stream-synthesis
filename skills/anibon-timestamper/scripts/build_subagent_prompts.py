import os
import json
import glob
import re
import sys

def build_prompts(workspace):
    chunks_dir = os.path.join(workspace, "chunks")
    signals_file = os.path.join(workspace, "signals.json")
    livechat_dir = os.path.join(workspace, "livechat")
    mood_file = os.path.join(workspace, "mood_555.json")
    prompts_dir = os.path.join(workspace, "prompts")
    os.makedirs(prompts_dir, exist_ok=True)

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

    # Group by 5
    groups = []
    group_size = 5
    for i in range(0, len(chunk_items), group_size):
        groups.append(chunk_items[i:i+group_size])

    template_path = os.path.join(os.path.dirname(__file__), "../references/subagent-prompt-template.md")
    with open(template_path, 'r', encoding='utf-8') as f:
        template_text = f.read()

    prev_topic = "Stream Intro / Chatting"
    for g_idx, group in enumerate(groups):
        group_prompt = []
        group_prompt.append(f"# Subagent Task: Process Group {g_idx + 1}/{len(groups)} (Chunks {group[0][0]} to {group[-1][0]})\n")
        group_prompt.append(f"PREVIOUS GROUP LAST TOPIC: {prev_topic}\n")

        for cnum, cpath, cid in group:
            with open(cpath, 'r', encoding='utf-8') as cf:
                chunk_xml = cf.read()

            csig = signals_map.get(cid, {})
            primary_topic = csig.get("primary_topic", "unknown")
            prev_topic = primary_topic

            # Livechat
            lc_path = os.path.join(livechat_dir, f"livechat_{cid}.txt")
            lc_content = "no livechat available"
            if os.path.exists(lc_path):
                with open(lc_path, 'r', encoding='utf-8') as lcf:
                    lc_content = lcf.read()

            # Mood
            cmood = mood_data.get(cid, {})
            mood_str = f"verdict: {cmood.get('verdict')}, tone: {cmood.get('tone')}, verbs: {cmood.get('verbs')}" if cmood else "no mood_555"

            try:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(chunk_xml)
                lines = []
                for el in root.findall("item"):
                    ts = el.attrib.get("timestamp", "00:00:00")
                    txt = (el.text or "").strip()
                    if txt:
                        lines.append(f"{ts} | {txt}")
                chunk_dialogue = "\n".join(lines)
            except Exception:
                chunk_dialogue = chunk_xml

            group_prompt.append(f"=== CHUNK {cnum} ({cid}) ===")
            group_prompt.append(f"PRIMARY TOPIC: {primary_topic}")
            group_prompt.append(f"LIVE-CHAT LOG:\n{lc_content[:2000]}")
            group_prompt.append(f"MOOD & TONE GUIDANCE: {mood_str}")
            group_prompt.append(f"DETECTION SIGNALS: {json.dumps(csig, ensure_ascii=False)}")
            group_prompt.append(f"TRANSCRIPT DIALOGUE:\n{chunk_dialogue}\n")

        # template_text is already baked into anibon-chunk-timestamper system prompt!
        out_path = os.path.join(prompts_dir, f"group_{g_idx+1:02d}.txt")
        with open(out_path, 'w', encoding='utf-8') as out_f:
            out_f.write("\n".join(group_prompt))

    print(f"Generated {len(groups)} group prompt files in {prompts_dir}")

if __name__ == "__main__":
    ws = sys.argv[1] if len(sys.argv) > 1 else "/Users/zenithth/youtube_W0bmqWlx4z4_workspace"
    build_prompts(ws)
