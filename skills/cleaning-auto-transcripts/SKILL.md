---
name: cleaning-auto-transcripts
description: Use when processing auto-generated YouTube transcripts that contain transcription errors, misspellings, or phonetic pronunciation anomalies.
---

# Cleaning Auto-Transcripts

A skill for processing, fetching, and noise-cleaning auto-generated YouTube transcripts that contain misspellings, speaker accent deviations, or incorrect transliterations. Maps erroneous text against a correct-spelling database to produce clean, complete downstream content.

## When to Use

- When downloading an auto-generated YouTube transcript for summarization or timestamping.
- When a speaker-specific error mapping file (Error Mapping) already exists for a given streamer/speaker, e.g. Pu Boat (FGO/ZZZ/Gaming VODs).
- When you need Space Normalization and disambiguation of overlapping terms.

** native speak language **
(เช่น การแยกแยะคำว่า "โรนิน" ออกจากคำว่า "เบโรนินะครับ")
** native speak language **

---

## STRICT Step-by-Step Guide
**CRITICAL DIRECTIVE**: You are FORBIDDEN from skipping steps. You must execute this process strictly sequentially.

### Step 1: MANDATORY Environment Check
**Action**: Run native tools to verify your execution environment before manipulating any files.
- **Bash**: `echo $SHELL && uname -a && command -v yt-dlp && command -v python3`
- **Windows PowerShell**: `$PSVersionTable.PSVersion; Get-Command yt-dlp; Get-Command python`
**CRITICAL**: You are FORBIDDEN from proceeding until you verify your shell and tools.

### Step 2: Prepare Workspace, Download, and Chunk Transcript
**Action**: Run the `prepare_video.py` script. This script automatically handles creating the `youtube_VIDEO_ID_workspace`, safely downloading the transcript with native `yt-dlp`, and cleaning/chunking it in one go.
- **Command**:
  Use the shared pipeline script:
  ```bash
  find $HOME/.gemini $HOME/.config/opencode $HOME/.agents \
    -path "*/anibon-stream-synthesis/scripts/prepare_video.py" 2>/dev/null | head -1
  ```

### Step 3: Verify Output
**Action**: Verify that `cleaned_transcript.json` (or the `chunks/` folder) was successfully generated inside the new workspace.
**CRITICAL PATH RULE**: File-reading tools DO NOT expand `$HOME` or `~`. You MUST use the true **absolute path**. Run `pwd` or `Get-Location` first to find the exact directory, then append the file path (e.g., `C:\Users\peter\youtube_VIDEO_ID_workspace\chunks\chunk_00.json`).

---

## Mapping Rules Structure

The file for storing misspelled-to-correct-spelling mappings is stored as JSON:
```json
{
  "mappings": [
    {
      "correct": "Resident Evil: Code Veronica",
      "patterns": ["veronica", "venomica", "venonica", "เบโรนิ", "เโรica"]
    },
    {
      "correct": "TMNT: The Last Ronin",
      "patterns": ["last ronin", "โรนิน"],
      "exclude_if_contains": ["เบโรนิน"]
    }
  ]
}
```

---

## Helper Scripts & Native Tools
**CRITICAL RULE (Ponytail Mode):** Never build reusable CLI abstractions for one-off JSON operations. Rely exclusively on native tools (`jq` or PowerShell `ConvertFrom-Json`) for searching, dumping, and previewing transcripts.

For convenient regex-based mapping cleanup, use:
- [clean_transcript.py](scripts/clean_transcript.py)

### Fetching Transcripts (Native)
**CRITICAL**: See **Step 2** for the exact command to fetch the transcript safely into an isolated workspace.

**Anti-Bot Block Handling (YouTube 429 Error / Sign-in required)**:
- **Local run**: Tell the user and ask which browser they use (e.g., `chrome`, `brave`, `edge`). Append `--cookies-from-browser <browser_name>` to the `yt-dlp` command. Do NOT guess the browser name or use random session strings.
- **OpenCode / Cloud Sandbox run**: If you are in an isolated cloud environment, `--cookies-from-browser` WILL FAIL. Ask the user to download the transcript locally and upload `raw_transcript.json` to the session workspace.

### clean_transcript.py Usage
Use simple positional arguments: `python clean_transcript.py <input.json> [custom_mappings.json] > output.json`

```bash
# Default mapping (outputs single JSON to stdout)
python scripts/clean_transcript.py raw_transcript.json > cleaned_transcript.json

# Custom mapping
python scripts/clean_transcript.py raw_transcript.json custom_mappings.json > cleaned_transcript.json

# Chunking mode (for MapReduce pipelines like anibon-timestamper)
# Use the --chunk flag to output segments with overlap directly to a folder, instead of stdout.
python scripts/clean_transcript.py raw_transcript.json --chunk --chunk-dir chunks --block 900 --overlap 60
```

### Transcript Operations (Native One-Liners)
**CRITICAL RULE**: Do NOT use your built-in `grep` or `search` tools to search JSON transcripts! You will lose the timestamps or encounter "No files found" errors. You MUST use the following PowerShell one-liners with **absolute paths**. Always enforce UTF-8 encoding so Thai characters are not corrupted into gibberish!
- **Search for keywords:**
  `powershell -c "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; (Get-Content -Encoding UTF8 'C:\Users\peter\youtube_VIDEO_ID_workspace\cleaned_transcript.json' -Raw | ConvertFrom-Json) | ? text -match 'keyword' | Select-Object start, text"`
- **Dump time range:**
  `powershell -c "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; (Get-Content -Encoding UTF8 'C:\Users\peter\youtube_VIDEO_ID_workspace\cleaned_transcript.json' -Raw | ConvertFrom-Json) | ? { $_.start -ge 1000 -and $_.start -le 1200 }"`
---

## Integration with Other Skills

When activating a summarization or timestamping skill, follow these steps:

1. **anibon-timestamper**:
   * **REQUIRED SUB-SKILL**: Use `cleaning-auto-transcripts` to clean the transcript file before running the timestamp script, for stable keyword matching.
2. **youtube-minutes-synthesis**:
   * **REQUIRED SUB-SKILL**: Switch to fetching and cleaning the transcript with `clean_transcript.py` as the base cleaning step (instead of using raw `fetch_transcript.py`) so the meeting-minutes report is free of transcription noise.

---

## Iron Rules

- **NEVER modify original timestamps**: During text cleaning, NEVER edit or adjust the `start` and `duration` fields of the original transcript.
- **Space Normalization first**: ALWAYS apply Space Normalization before any comparison. Uneven spacing breaks word mapping.
- **Handle exclusions carefully**: Manage overlapping-term exclusions strictly via the `exclude_if_contains` system in the script at all times.
- **NEVER use Python YouTube Transcript APIs**: Do NOT write `python3 -c "from youtube_transcript_api import ..."` or install extra dependencies. Use standard native `yt-dlp --write-auto-subs` to fetch transcripts.
- **Ask user and log unknown or mismatched search terms**: If you try to search for an unfamiliar or distorted word using search tools, but the search results do not seem to fit the spoken context (e.g. searching "Bฟet" returns food buffets but context is about law/succession), **stop and ask the user directly in the chat**. Display the mismatched word, its exact timestamp, and the surrounding transcript sentence/segment. Once the user clarifies the correct meaning, save the corrected phonetic mapping back to `default_mappings.json` or custom mappings.
- **Low-Context AI Defense (< 8k context)**: If your context limit is extremely restricted (e.g., `gemma4:31b` or `e2b`), NEVER run unbounded searches, previews, or full file reads on transcripts or mappings files. You MUST strictly limit output by piping to `head` / `Select-Object -First`, adding `--limit 5` where applicable, or keeping `dump` ranges strictly under 60 seconds. Rely entirely on the python script for full-scale processing to protect your context window.



