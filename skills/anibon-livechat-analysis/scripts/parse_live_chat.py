#!/usr/bin/env python3
import json
import sys
import os
import argparse

def parse_live_chat(json_path, output_dir, chunk_minutes=90, raw_events=None):
    os.makedirs(output_dir, exist_ok=True)
    
    events = []  # (sec, time_str, text)
    with open(json_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                action = data.get('replayChatItemAction', {}).get('actions', [{}])[0]
                
                # Check for chat item
                item = action.get('addChatItemAction', {}).get('item', {})
                text_msg = item.get('liveChatTextMessageRenderer', {})
                paid_msg = item.get('liveChatPaidMessageRenderer', {})
                sticker_msg = item.get('liveChatPaidStickerRenderer', {})
                
                time_ms = int(data.get('replayChatItemAction', {}).get('videoOffsetTimeMsec', 0))
                sec = time_ms // 1000
                h = sec // 3600
                m = (sec % 3600) // 60
                s = sec % 60
                time_str = f"{h:02d}:{m:02d}:{s:02d}"
                
                if text_msg:
                    author = text_msg.get('authorName', {}).get('simpleText', 'Unknown')
                    runs = text_msg.get('message', {}).get('runs', [])
                    msg_text = "".join([r.get('text', '') for r in runs]).strip()
                    if msg_text:
                        events.append((sec, time_str, f"[{time_str}] {author}: {msg_text}"))
                elif paid_msg:
                    author = paid_msg.get('authorName', {}).get('simpleText', 'Unknown')
                    amount = paid_msg.get('purchaseAmountText', {}).get('simpleText', '')
                    runs = paid_msg.get('message', {}).get('runs', [])
                    msg_text = "".join([r.get('text', '') for r in runs]).strip()
                    events.append((sec, time_str, f"[{time_str}] 💰 SUPERCHAT ({amount}) from {author}: {msg_text}"))
                elif sticker_msg:
                    author = sticker_msg.get('authorName', {}).get('simpleText', 'Unknown')
                    amount = sticker_msg.get('purchaseAmountText', {}).get('simpleText', '')
                    events.append((sec, time_str, f"[{time_str}] 🎨 STICKER ({amount}) from {author}"))
            except Exception:
                continue

    events.sort(key=lambda x: x[0])

    # Raw one-line-per-event feed (seconds-prefixed) so align_live_chat.py can
    # slice events to any transcript chunk window. Format: <sec>\t<[HH:MM:SS]> msg
    if raw_events:
        with open(raw_events, 'w', encoding='utf-8') as f:
            for sec, ts, line in events:
                f.write(f"{sec}\t{line}\n")
        print(f"[*] Wrote raw event feed: {raw_events} ({len(events)} events)")

    if not events:
        print("[!] No live chat events found.")
        return

    chunk_sec = chunk_minutes * 60
    max_sec = events[-1][0]
    num_chunks = (max_sec // chunk_sec) + 1
    
    for i in range(num_chunks):
        start_t = i * chunk_sec
        end_t = (i + 1) * chunk_sec
        chunk_lines = [line for sec, ts, line in events if start_t <= sec < end_t]
        
        chunk_file = os.path.join(output_dir, f"livechat_chunk_{i+1}.txt")
        with open(chunk_file, 'w', encoding='utf-8') as f:
            for l in chunk_lines:
                f.write(l + "\n")
        print(f"[*] Wrote Chunk {i+1}: {len(chunk_lines)} messages ({start_t//3600:02d}:{(start_t%3600)//60:02d}:00 - {end_t//3600:02d}:{(end_t%3600)//60:02d}:00) -> {chunk_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse YouTube LiveChat JSON lines into chunked text files.")
    parser.add_argument("json_path", help="Path to .live_chat.json file")
    parser.add_argument("-o", "--output-dir", default="livechat_chunks", help="Output directory for text chunks")
    parser.add_argument("--chunk-minutes", type=int, default=90, help="Minutes per chunk (default: 90)")
    parser.add_argument("--raw-events", default=None, help="Optional: also write a seconds-prefixed event feed for chunk alignment")
    args = parser.parse_args()
    
    parse_live_chat(args.json_path, args.output_dir, args.chunk_minutes, args.raw_events)
