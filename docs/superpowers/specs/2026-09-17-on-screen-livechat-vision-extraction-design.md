# Design Specification: On-Screen LiveChat Vision Extraction

**Date**: 2026-09-17  
**Status**: Approved (Draft Spec)  
**Topic**: On-screen burned-in live chat extraction via vision proxy for edited Anibon livestreams  

---

## 1. Background & Problem

When Pu Boat (โบ๊ต / PhuBoat) edits past Anibon livestreams in YouTube Studio (e.g. trimming copyrighted segments, dead air, or long breaks), YouTube permanently disables and removes the `.live_chat.json` replay stream. Downstream timestamping and synthesis pipelines that rely on chat reactions, meme spikes, and viewer interactions are left without chat data.

However, the video broadcast itself contains an OBS burned-in live chat overlay on screen. Custom emotes and stickers appear as rendered images/icons rather than text tokens. 

This specification defines an on-demand vision extraction tool that crops the burned-in chat region, recognizes Thai messages and authors, translates picture emotes into standard token shortcuts (e.g., `:_Nerd:`, `:_CunnyBoat:`), and formats the output identically to standard YouTube live chat event feeds.

---

## 2. Goals & Non-Goals

### Goals
- **Replay Check First**: Always check if `.live_chat.json` is available from YouTube first. Only trigger vision extraction if missing or empty.
- **On-Demand Scope**: Support targeted spot-inspection for specific time ranges (e.g., 1–3 minute segments) without burning tokens on continuous multi-hour stream scanning.
- **Auto-Detect Overlay Layout**: Automatically detect whether the chat overlay is positioned at the **bottom-right corner** or **left side**, and crop accordingly.
- **Picture Emote Grounding**: Translate visual channel emotes and stickers into standard text codes (`:_Nerd:`, `:_CunnyBoat:`, `:_MonkeyBoat:`, `555`) using the channel emoji dictionary.
- **Full Downstream Compatibility**: Output standard tab-separated raw event lines (`<sec>\t[HH:MM:SS] Author: message`) so `align_live_chat.py` and `anibon-chunk-timestamper` can consume it with zero architectural changes.

### Non-Goals
- Full continuous 4-hour stream OCR scanning (prohibitive token and compute cost).
- Replacement of `parse_live_chat.py` when official `.live_chat.json` is present.

---

## 3. Architecture & Data Flow

```
+-------------------------------------------------------------+
|                      Target Time Range                      |
|                  (e.g., 00:10:00 - 00:12:00)                |
+-------------------------------------------------------------+
                              |
                              v
             +---------------------------------+
             |   LiveChat Availability Gate    |
             +---------------------------------+
               /                             \
     (File exists / dl ok)         (Missing / Edited Stream)
             /                                 \
            v                                   v
+-----------------------+           +-----------------------+
|  parse_live_chat.py   |           | Visual Extraction Flow|
+-----------------------+           +-----------------------+
                                                |
                                                v
                                    +-----------------------+
                                    |   Video Acquisition   |
                                    | (Local MP4 / yt-dlp   |
                                    |  720p section slice)  |
                                    +-----------------------+
                                                |
                                                v
                                    +-----------------------+
                                    |  Layout Auto-Detector |
                                    | (Probe candidate ROIs)|
                                    +-----------------------+
                                                |
                                                v
                                    +-----------------------+
                                    |  ffmpeg ROI Cropping  |
                                    |  (1 frame / 3-5 sec)  |
                                    +-----------------------+
                                                |
                                                v
                                    +-----------------------+
                                    | `agy` Gemini Vision   |
                                    | OCR + Emote Mapping   |
                                    +-----------------------+
                                                |
                                                v
                                    +-----------------------+
                                    | Deduplication & Parse |
                                    +-----------------------+
                                                |
                                                v
                                    +-----------------------+
                                    | Raw Event Feed Output |
                                    |  (<sec>\t[HH:MM:SS]..) |
                                    +-----------------------+
```

---

## 4. Detailed Component Design

### 4.1 Video Acquisition
- Checks if a full local video file (`.mp4`, `.webm`, `.mkv`) exists in the stream workspace.
- If not, uses `yt-dlp` to download only the requested target time range at 720p:
  ```bash
  yt-dlp --cookies-from-browser chrome \
    --download-sections "*HH:MM:SS-HH:MM:SS" \
    -f "bestvideo[height<=720]+bestaudio/best[height<=720]" \
    -o "slice_%(id)s.%(ext)s" "https://www.youtube.com/watch?v=VIDEO_ID"
  ```
- Fast (~1–3s download time, ~500KB–2MB file size).

### 4.2 Layout Auto-Detection & ROI Bounding Boxes
Probe a single sample frame from the target range to detect active chat placement between two candidate regions:
- **Candidate A (Bottom-Right)**:
  - Width: `25%` of video width (`in_w*0.25`)
  - Height: `42%` of video height (`in_h*0.42`)
  - X offset: `75%` of video width (`in_w*0.75`)
  - Y offset: `54%` of video height (`in_h*0.54`)
- **Candidate B (Left-Side)**:
  - Width: `28%` of video width (`in_w*0.28`)
  - Height: `60%` of video height (`in_h*0.60`)
  - X offset: `1%` of video width (`in_w*0.01`)
  - Y offset: `22%` of video height (`in_h*0.22`)

The detector samples 1 frame, checks text density/presence via a quick vision probe or crop heuristic, and locks the active ROI for the slice.

### 4.3 Frame Extraction & Cropping
Extracts 1 frame every 3 to 5 seconds across the target window using `ffmpeg`:
```bash
ffmpeg -i target_slice.webm -vf "fps=1/4,crop=in_w*0.25:in_h*0.42:in_w*0.75:in_h*0.54" \
  -q:v 2 frames/chat_%03d.jpg
```
Cropping drops ~90% of irrelevant image pixels, ensuring ultra-crisp typography and low token overhead.

### 4.4 Vision Prompting & Emote Disambiguation
Each frame (or batch of consecutive frames) is processed through `agy` with Gemini 3.6 Flash.

**Prompt Template**:
```text
You are an expert OCR and YouTube livestream chat transcript parser.
Analyze this cropped live chat image from an Anibon stream.

1. Extract all visible chat messages from top to bottom.
2. For each message, extract:
   - Author username (e.g. @user)
   - Message text exactly as written in Thai/English.
   - Any SuperChat donation amount if highlighted as a paid message.
3. Map rendered picture emotes to standard channel emote tags using this reference:
   - Yellow crying face with glasses: :_CunnyBoat:
   - Monkey pose Boat: :_MonkeyBoat:
   - Pushing glasses finger up nerd face: :_Nerd:
   - Grinning mischievous face: :_Grind:
   - Standing fish meme: :_Ripfish:
   - Plush doll on bed: :_noname:
   - Squinting confused face: :_What:
   - Wide eyes Poggers: :_WOW:
   - Head back bliss face: :_Ahh:
   - Deadpan flat face: :_Meh:
   - Holding orange: :_BoatSOM:
   - Camo military uniform: :_Tahaan:
   - Yellow shirt polite smile: :_KonDee:
   - Sipping tea cup: :_Tea:
   - Blue smiling face: :face-blue-smiling:
   - Pink waving hand: :hand-pink_waving:

Output JSON format:
[
  {"author": "@username", "text": "message content with :_Emote: tags", "superchat": null}
]
```

### 4.5 Deduplication & Time Assignment
Because chat overlays scroll upward continuously over time:
- Maintain a rolling set of `(author, normalized_text)`.
- When a message appears in frame $N$ and frame $N+1$, keep the earliest timestamp.
- Calculate approximate seconds offset based on frame index ($T_{start} + i \times \text{interval}$).
- Output as tab-separated lines:
  ```text
  <sec>\t[HH:MM:SS] Author: message text
  ```

---

## 5. File & CLI Interface

### Script Location
`skills/anibon-livechat-analysis/scripts/extract_visual_livechat.py`

### CLI Arguments
```text
usage: extract_visual_livechat.py [-h] [--video-id VIDEO_ID] [--video-path VIDEO_PATH]
                                 [--range START-END] [--output OUTPUT]
                                 [--force-pos {auto,bottom-right,left}]
                                 [--fps FPS]
```

### Integration Points
1. **`anibon-livechat-analysis`**: Adds fallback instructions in `SKILL.md` when `.live_chat.json` is not downloadable.
2. **`anibon-timestamper`**: When preparing chunk context for chunks that have missing livechat, can invoke `extract_visual_livechat.py` on-demand for critical peak ranges.
3. **`align_live_chat.py`**: Reads generated raw event files transparently.

---

## 6. Verification Plan

### Automated Tests
- Unit test for layout ROI calculation and coordinate validation (`test_visual_livechat_roi.py`).
- Unit test for scroll deduplication algorithm (`test_chat_dedup.py`).

### End-to-End Real Stream Verification
- Verify against real livestream `nF7pCwCZCaE` (tested during spike):
  - Confirms bottom-right layout detection.
  - Confirms extraction of `@infinity8078: :_Nerd: :_Nerd: :_Nerd: :_Nerd:`.
  - Confirms output file generates valid tab-separated raw event feed parseable by `align_live_chat.py`.
