"""Deduplicate scrolling livechat messages across sampled frames."""

from typing import Any


def sec_to_hhmmss(sec: int) -> str:
    """Format seconds integer into HH:MM:SS string."""
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_raw_event(
    sec: int, author: str, text: str, superchat: str | None = None
) -> str:
    """Format a chat message into a YouTube LiveChat raw event line (<sec>\\t[HH:MM:SS] ...)."""
    ts = sec_to_hhmmss(sec)
    if superchat:
        return f"{sec}\t[{ts}] 💰 SUPERCHAT ({superchat}) from {author}: {text}"
    return f"{sec}\t[{ts}] {author}: {text}"


def deduplicate_frames_messages(
    frames_data: list[dict[str, Any]],
    window_sec: int | None = None,
) -> list[tuple[int, str]]:
    """Deduplicate scrolling messages across sampled frames and format into raw event lines.

    Args:
        frames_data: List of frame dictionaries containing:
            - 'sec': Timestamp in seconds for the sampled frame
            - 'messages': List of parsed message dicts with 'author', 'text', and optional 'superchat'
        window_sec: Optional time window in seconds for deduplication. If None,
            retains global set behavior across all frames. If specified, tracks
            the last seen timestamp per message and allows the message again if
            sec - last_sec > window_sec.

    Returns:
        Sorted list of tuples (sec, formatted_event_string)
    """
    seen_set: set[tuple[str, str]] = set()
    seen_map: dict[tuple[str, str], int] = {}
    events: list[tuple[int, str]] = []

    for frame in frames_data:
        sec = int(frame.get("sec", 0))
        for msg in frame.get("messages", []):
            author = msg.get("author", "").strip()
            text = msg.get("text", "").strip()
            sc = msg.get("superchat")
            key = (author.lower(), text)
            if not key[0] or not key[1]:
                continue
            if window_sec is None:
                if key in seen_set:
                    continue
                seen_set.add(key)
            else:
                last_sec = seen_map.get(key)
                if last_sec is not None and (sec - last_sec) <= window_sec:
                    continue
                seen_map[key] = sec
            formatted = format_raw_event(sec, author, text, superchat=sc)
            events.append((sec, formatted))

    events.sort(key=lambda x: x[0])
    return events

