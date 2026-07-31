"""Stream analysis functions: chunk classification, gap detection, block sizing.

Consumers (before extraction):
  classify_chunk            — anibon_analyzer_core.py:65
  detect_timeline_gaps      — anibon_analyzer_core.py:79
  calculate_youtube_blocks  — anibon_analyzer_core.py:100
"""

KEYWORDS: dict[str, list[str]] = {
    "tokusatsu": [
        "ไรเดอร์", "rider", "เซนไต", "sentai", "อุลตร้าแมน", "ultraman",
        "กาโร่", "garo", "เฮนชิน", "henshin", "เข็มขัด", "ของเล่น", "dx",
        "zeztz", "myth", "ไมสึ", "gavv", "geats", "gotchard", "tokusatsu",
    ],
    "fgo": ["fgo", "fate", "grand order", "servant", "gacha", "chaldea"],
    "ygo": ["yugioh", "ygo", "yu-gi-oh", "การ์ดยูกิ"],
    "gaming": ["เล่นเกม", "เกม", "บอส", "boss", "gameplay"],
    "royal": ["อิมู", "imu", "มังกรฟ้า", "112", "ร.10", "สุทิดา", "พระองค์ภา"],
}


def classify_chunk(chunk: dict, keywords: dict | None = None) -> list[str]:
    """Return list of matching categories for a chunk.

    Each chunk has 'items', each with 'text'. Full text is joined and
    matched against keyword lists. Returns ["unknown"] if no match.
    """
    if keywords is None:
        keywords = KEYWORDS

    items = chunk.get("items", [])
    full_text = " ".join(it.get("text", "") for it in items).lower()

    matched = []
    for category, words in keywords.items():
        if any(w in full_text for w in words):
            matched.append(category)

    return matched if matched else ["unknown"]


def detect_timeline_gaps(chunks: list[dict], gap_limit_sec: int = 600) -> list[dict]:
    """Detect gaps between chunks that exceed gap_limit_sec.

    Returns list of {from_ts, to_ts, gap_sec}.
    """
    gaps = []
    for i in range(1, len(chunks)):
        prev = chunks[i - 1]
        curr = chunks[i]
        diff = curr["start_sec"] - prev["end_sec"]
        if diff > gap_limit_sec:
            prev_ts = prev["items"][0]["timestamp"] if prev.get("items") else "unknown"
            curr_ts = curr["items"][0]["timestamp"] if curr.get("items") else "unknown"
            gaps.append({"from_ts": prev_ts, "to_ts": curr_ts, "gap_sec": diff})
    return gaps


def calculate_youtube_blocks(chunks: list[dict], warn_bytes: int = 3500) -> list[dict]:
    """Group consecutive chunks by category and report byte sizes.

    Returns list of {category, start_ts, end_ts, byte_size, status}.
    Status is "OK" / "WARN" / "OVER" based on byte size thresholds.
    """
    blocks = []
    if not chunks:
        return blocks

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
            if byte_size > 4500:
                status = "OVER"
            elif byte_size > warn_bytes:
                status = "WARN"

            blocks.append({
                "category": curr_category,
                "start_ts": start_ts,
                "end_ts": last_ts,
                "byte_size": byte_size,
                "status": status,
            })
            curr_category = cat
            curr_text = text
            start_ts = chunk["items"][0]["timestamp"] if chunk.get("items") else ts
            last_ts = ts
        else:
            curr_text += " " + text
            last_ts = ts

    # Last block
    byte_size = len(curr_text.encode("utf-8"))
    status = "OK"
    if byte_size > 4500:
        status = "OVER"
    elif byte_size > warn_bytes:
        status = "WARN"
    blocks.append({
        "category": curr_category,
        "start_ts": start_ts,
        "end_ts": last_ts,
        "byte_size": byte_size,
        "status": status,
    })

    return blocks
