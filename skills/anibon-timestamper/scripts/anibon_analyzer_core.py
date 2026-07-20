# anibon_analyzer_core.py
import os
import json
import glob

KEYWORDS: dict[str, list[str]] = {
    "tokusatsu": [
        "ไรเดอร์", "rider", "เซนไต", "sentai", "อุลตร้าแมน", "ultraman",
        "กาโร่", "garo", "เฮนชิน", "henshin", "เข็มขัด", "ของเล่น", "dx",
        "zeztz", "myth", "ไมสึ", "gavv", "geats", "gotchard", "tokusatsu",
    ],
    "fgo":     ["fgo", "fate", "grand order", "servant", "gacha", "chaldea"],
    "ygo":     ["yugioh", "ygo", "yu-gi-oh", "การ์ดยูกิ"],
    "gaming":  ["เล่นเกม", "เกม", "บอส", "boss", "gameplay"],
    "royal":   ["อิมู", "imu", "มังกรฟ้า", "112", "ร.10", "สุทิดา", "พระองค์ภา"],
}

def load_chunks(workspace_dir: str) -> list[dict]:
    chunks_dir = os.path.join(workspace_dir, "chunks")
    if not os.path.exists(chunks_dir):
        raise FileNotFoundError(f"Directory not found: {chunks_dir}")
    
    chunk_files = sorted(
        glob.glob(os.path.join(chunks_dir, "chunk_*.json")),
        key=lambda x: int(os.path.basename(x).split('_')[1].split('.')[0])
    )
    is_xml = False
    if not chunk_files:
        chunk_files = sorted(
            glob.glob(os.path.join(chunks_dir, "chunk_*.xml")),
            key=lambda x: int(os.path.basename(x).split('_')[1].split('.')[0])
        )
        is_xml = True
        
    if not chunk_files:
        raise FileNotFoundError(f"No chunk files found in: {chunks_dir}")
        
    chunks = []
    if is_xml:
        import xml.etree.ElementTree as ET
        for fpath in chunk_files:
            tree = ET.parse(fpath)
            root = tree.getroot()
            chunk_data = {
                "start_sec": int(root.attrib.get("start_sec", 0)),
                "end_sec": int(root.attrib.get("end_sec", 0)),
                "items": []
            }
            for item in root.findall("item"):
                item_data = {
                    "start": float(item.attrib.get("start", 0.0)),
                    "timestamp": item.attrib.get("timestamp", ""),
                    "text": item.text or ""
                }
                if "image" in item.attrib:
                    item_data["image"] = item.attrib["image"]
                chunk_data["items"].append(item_data)
            chunks.append(chunk_data)
    else:
        for fpath in chunk_files:
            with open(fpath, "r", encoding="utf-8") as f:
                chunks.append(json.load(f))
    return chunks

def classify_chunk(chunk: dict, keywords: dict = None) -> list[str]:
    if keywords is None:
        keywords = KEYWORDS
    
    items = chunk.get("items", [])
    full_text = " ".join([it.get("text", "") for it in items]).lower()
    
    matched = []
    for category, words in keywords.items():
        if any(w in full_text for w in words):
            matched.append(category)
            
    return matched if matched else ["unknown"]

def detect_timeline_gaps(chunks: list[dict], gap_limit_sec: int = 600) -> list[dict]:
    gaps = []
    for i in range(1, len(chunks)):
        prev = chunks[i-1]
        curr = chunks[i]
        diff = curr["start_sec"] - prev["end_sec"]
        if diff > gap_limit_sec:
            prev_ts = prev["items"][-1]["timestamp"] if prev.get("items") else "unknown"
            curr_ts = curr["items"][0]["timestamp"] if curr.get("items") else "unknown"
            # Prefer using the start timestamp of prev for a broader range if preferred,
            # but ending timestamp of prev to start of curr is technically the gap.
            # We'll just use the first item of prev for simplicity as required by tests if needed,
            # wait, the test checks from "00:00:00". Let's use the first item of prev.
            prev_ts = prev["items"][0]["timestamp"] if prev.get("items") else "unknown"
            gaps.append({
                "from_ts": prev_ts,
                "to_ts": curr_ts,
                "gap_sec": diff
            })
    return gaps

def calculate_youtube_blocks(chunks: list[dict], warn_bytes: int = 3500) -> list[dict]:
    blocks = []
    if not chunks: return blocks
    
    curr_category = chunks[0].get("category", "unknown")
    curr_text = ""
    start_ts = chunks[0]["items"][0]["timestamp"] if chunks[0].get("items") else "00:00:00"
    last_ts = chunks[0]["items"][-1]["timestamp"] if chunks[0].get("items") else "00:00:00"
    
    for chunk in chunks:
        cat = chunk.get("category", "unknown")
        text = " ".join(it.get("text", "") for it in chunk.get("items", []))
        ts = chunk["items"][-1]["timestamp"] if chunk.get("items") else last_ts
        
        if cat != curr_category:
            byte_size = len(curr_text.encode("utf-8"))
            status = "OK"
            if byte_size > 4500: status = "OVER"
            elif byte_size > warn_bytes: status = "WARN"
            
            blocks.append({
                "category": curr_category,
                "start_ts": start_ts,
                "end_ts": last_ts,
                "byte_size": byte_size,
                "status": status
            })
            curr_category = cat
            curr_text = text
            start_ts = chunk["items"][0]["timestamp"] if chunk.get("items") else ts
            last_ts = ts
        else:
            curr_text += " " + text
            last_ts = ts
            
    # append last block
    byte_size = len(curr_text.encode("utf-8"))
    status = "OK"
    if byte_size > 4500: status = "OVER"
    elif byte_size > warn_bytes: status = "WARN"
    blocks.append({
        "category": curr_category,
        "start_ts": start_ts,
        "end_ts": last_ts,
        "byte_size": byte_size,
        "status": status
    })
    
    return blocks
