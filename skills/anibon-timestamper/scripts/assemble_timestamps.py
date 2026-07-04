import re
import argparse
import json

def parse_time(ts_str):
    parts = list(map(int, ts_str.split(":")))
    if len(parts) == 3:
        return parts[0]*3600 + parts[1]*60 + parts[2]
    elif len(parts) == 2:
        return parts[0]*60 + parts[1]
    return 0

def assemble_logic(lines: list[str], topics: list[dict], limit_bytes: int = 4500, max_chunk_bytes: int = 2400) -> list[str]:
    entries_dict = {}
    pattern = re.compile(r'^(\d{2}:\d{2}:\d{2})\s*-\s*\[(.*?)\]\s*(.*)$')
    for line in lines:
        match = pattern.match(line)
        if match:
            entries_dict[match.group(1)] = {"sec": parse_time(match.group(1)), "ts": match.group(1), "line": line}
    entries = list(entries_dict.values())
            
    # Group by topic using simple iteration (Ponytail)
    groups = {i: [] for i in range(len(topics))}
    topic_starts = [parse_time(t["start"]) for t in topics]
    for entry in entries:
        idx = max((i for i, start_sec in enumerate(topic_starts) if entry["sec"] >= start_sec), default=0)
        groups[idx].append(entry)
        
    output = ["# วิดีโอสตรีม ANIBON - ทริปส์และข่าวสารเกมกาชา\n"]
    sec_num = 1
    
    for i, t in enumerate(topics):
        topic_entries = groups[i]
        if not topic_entries: continue
        
        bytes_total = len("\n".join(e["line"] for e in topic_entries).encode("utf-8"))
        estimated = bytes_total + 300
        
        # Floor division instead of math.ceil (Ponytail)
        num_parts = (estimated + max_chunk_bytes - 1) // max_chunk_bytes if estimated > limit_bytes else 1
        items_per = (len(topic_entries) + num_parts - 1) // num_parts
        
        for p in range(num_parts):
            chunk = topic_entries[p * items_per : (p + 1) * items_per]
            if not chunk: continue
            
            part_suffix = f" (ตอนที่ {p+1}/{num_parts})" if num_parts > 1 else ""
            summary = f"{t['summary']}{part_suffix}"
            topic_str = f"{t['topic']} - ตอนที่ {p+1}" if num_parts > 1 else t["topic"]
            
            output.append("═════════════════════════════════════════════════════════")
            output.append(f"📌 ส่วนที่ {sec_num}: {summary}")
            output.append(f"(หัวข้อ: {topic_str} | ⏱ เริ่ม: {chunk[0]['ts']})")
            output.append("═════════════════════════════════════════════════════════")
            output.extend(e["line"] for e in chunk)
            output.append("")
            sec_num += 1
            
    return output

def main():
    parser = argparse.ArgumentParser(description="Assemble timestamps into split markdown.")
    parser.add_argument("input", help="Merged timestamps file")
    parser.add_argument("--topics", required=True, help="Topics JSON config file")
    parser.add_argument("-o", "--output", help="Output MD file (stdout if omitted)")
    args = parser.parse_args()
    
    with open(args.input, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
        
    with open(args.topics, "r", encoding="utf-8") as f:
        topics = json.load(f)
        
    results = assemble_logic(lines, topics)
    
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write("\n".join(results) + "\n")
    else:
        for r in results: print(r)

if __name__ == "__main__":
    main()
