"""Markdown formatting for timestamp parts (separator-block format).

Consumers (before extraction):
  format_markdown  — pack_timestamps.py:113 (root) / pack_timestamps.py:473 (timestamper)
"""


def format_markdown(parts: list, doc_title: str) -> str:
    """Format parts into separator-block markdown.

    Each part dict has: title (str), start (str), entries (list of dicts with 'raw' key).
    Output format matches anibon-timestamper summarizer spec.
    """
    out = [f"# {doc_title}", ""]
    for i, p in enumerate(parts, 1):
        out.append("═════════════════════════════════════════════════════════")
        out.append(f" ส่วนที่ {i}: {p['title']} (⏱ เริ่ม: {p['start']})")
        out.append("═════════════════════════════════════════════════════════")
        for entry in p["entries"]:
            out.append(entry["raw"])
        out.append("")
    return "\n".join(out)


def write_parts_json(parts: list, path):
    """Write parts as JSON for reassembly.

    Each part output: {title, start, body} where body is newline-joined raw lines.
    """
    import json
    from pathlib import Path

    out = []
    for p in parts:
        body_lines = [e["raw"] for e in p["entries"]]
        out.append({
            "title": p["title"],
            "start": p["start"],
            "body": "\n".join(body_lines),
        })
    Path(path).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[*] Wrote parts.json with {len(out)} sections → {path}", file=__import__("sys").stderr)
