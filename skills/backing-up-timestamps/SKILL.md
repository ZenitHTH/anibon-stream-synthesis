---
name: backing-up-timestamps
description: Use when stream timestamping is complete in youtube_*_workspace, when archiving timestamps to timestamp_workspace, or when organizing and moving backed-up stream workspaces.
---

# Backing Up Timestamps to `timestamp_workspace`

## Overview

Centralized workflow for ingesting finalized stream timestamps into the [`timestamp_workspace`](file:///Users/zenithth/timestamp_workspace) catalog and cleanly archiving heavy raw workspaces into [`/Users/zenithth/youtube_workspaces/backed_up/`](file:///Users/zenithth/youtube_workspaces/backed_up/).

**Core principle**: `timestamp_workspace` is a lightweight, version-controlled catalog of clean markdown files and metadata; raw intermediate workspace directories (containing gigabytes of audio, frames, and JSONs) live in `~/youtube_workspaces/backed_up/`, NEVER inside git.

---

## When to Use

- When an `anibon-timestamper` run completes and `output.md` (or `timestamps_packed.md`) is finalized.
- When user asks to "backup workspace into timestamp_workspace", "catalog timestamps", or "organize workspaces".
- When new `youtube_*_workspace` folders in `~` need to be audited and archived.

### When NOT to Use

- When timestamp generation is still in-flight (subagents still running or gaps remain).
- For non-stream workspaces or raw media editing temporary files.

---

## The Iron Rules

1. **IMPORT FIRST, MOVE ONLY IF BACKED UP**: Never move a workspace into `youtube_workspaces/backed_up/` before `import_workspace.py` confirms successful parsing and catalog update. If import fails, DO NOT MOVE the directory.
2. **ACTIVE WORKSPACES ONLY**: Never move `.zip` archives or directories ending in `_Backup` (e.g. `youtube_W0bmqWlx4z4_workspace_Backup`). Leave them in `~`.
3. **NEVER COPY RAW MEDIA TO GIT**: Never copy whole workspaces, audio slices, or frames into `timestamp_workspace`. Only markdown summaries and catalog metadata belong in `timestamp_workspace`.

---

## Canonical Paths

| Component | Path | Description |
|-----------|------|-------------|
| Master Catalog | `/Users/zenithth/timestamp_workspace/` | Git repo for index, README, and markdown stamps |
| Ingestion Script | `/Users/zenithth/timestamp_workspace/import_workspace.py` | Normalizes stamps, updates `catalog.json` & `README.md` |
| Markdown Store | `/Users/zenithth/timestamp_workspace/by_video_id/` | `timestamp_<video_id>.md` files |
| Master JSON | `/Users/zenithth/timestamp_workspace/metadata/catalog.json` | Master structured index |
| Archived Workspaces | `/Users/zenithth/youtube_workspaces/backed_up/` | Destination for raw source workspaces |

---

## Workflow (Linear, Top-to-Bottom)

### 1. Locate Source Workspace & Verify Candidates

A valid workspace directory MUST contain at least one recognized timestamp markdown file:
- `output.md` (standard pipeline output)
- `timestamps_packed.md` (packed multi-part output)
- `timestamp_<video_id>.md`
- `assembled_timestamps.md`

```bash
# Check candidate exists and is non-empty (>0 bytes)
ls -lh ~/youtube_<video_id>_workspace/output.md
```

### 2. Preview Ingestion (Dry-Run)

Always verify candidate discovery, title resolution, and timestamp count before modifying files:

```bash
python3 /Users/zenithth/timestamp_workspace/import_workspace.py   ~/youtube_<video_id>_workspace   --dry-run
```

### 3. Execute Ingestion

Run the ingestion tool. It automatically:
- Extracts title and upload date (via `video_info.json`, `yt-dlp`, or `*.live_chat.json` fallback).
- Injects standard header metadata (`# Title`, `YouTube Video ID`, `Workspace Directory`, `Total Timestamps`).
- Preserves `═════` part divider blocks and tag formatting.
- Writes `by_video_id/timestamp_<video_id>.md`.
- Appends/updates `metadata/catalog.json` sorted chronologically descending.
- Re-renders the catalog table in `README.md`.

```bash
python3 /Users/zenithth/timestamp_workspace/import_workspace.py   ~/youtube_<video_id>_workspace
```

*For batch imports across multiple workspaces:*
```bash
python3 /Users/zenithth/timestamp_workspace/import_workspace.py   ~/youtube_*_workspace
```

### 4. Verify Catalog Success BEFORE Moving

Confirm that the output files exist and catalog was updated:

```bash
# Verify markdown was written
test -s /Users/zenithth/timestamp_workspace/by_video_id/timestamp_<video_id>.md && echo "Verified"

# Verify video_id is present in catalog.json
grep -q '"video_id": "<video_id>"' /Users/zenithth/timestamp_workspace/metadata/catalog.json && echo "Cataloged"
```

### 5. Move Verified Workspace to Archive

ONLY after Step 4 passes, relocate the raw workspace:

```bash
mkdir -p /Users/zenithth/youtube_workspaces/backed_up
mv ~/youtube_<video_id>_workspace /Users/zenithth/youtube_workspaces/backed_up/
```

*Update `workspace_path` in `catalog.json` to match the new location:*
```bash
python3 -c "
import json
cat = json.load(open('/Users/zenithth/timestamp_workspace/metadata/catalog.json'))
for e in cat:
    if e['video_id'] == '<video_id>':
        e['workspace_path'] = '/Users/zenithth/youtube_workspaces/backed_up/youtube_<video_id>_workspace'
json.dump(cat, open('/Users/zenithth/timestamp_workspace/metadata/catalog.json', 'w'), ensure_ascii=False, indent=2)
"
```

### 6. Commit Catalog Changes

```bash
cd /Users/zenithth/timestamp_workspace
git add by_video_id/timestamp_<video_id>.md metadata/catalog.json README.md
git commit -m "feat(catalog): backup <video_id> timestamps and update catalog/README"
```

---

## Common Mistakes & Solutions

| Mistake | Reality / Fix |
|---------|---------------|
| Moving workspace before import | Violates "if doesn't backup, don't move dir". Run `import_workspace.py` first. |
| Moving `.zip` or `_Backup` folders | These must remain in `~` untouched. Filter using regex `^youtube_[A-Za-z0-9_-]+_workspace$`. |
| Private stream causes `yt-dlp` error | `import_workspace.py` falls back to `live_chat.json` timestamp to obtain broadcast date automatically. |
| Copying raw chunks into `timestamp_workspace` | Git repo bloat. Only markdown and metadata go to `timestamp_workspace`. |
| Forgetting to update `workspace_path` | Keep `metadata/catalog.json` synchronized when relocating workspaces. |

---

## Red Flags - STOP and Verify

- Workspace has 0 timestamps detected.
- `by_video_id/timestamp_<video_id>.md` is 0 bytes or missing.
- Moving a folder named `*_Backup` or `*.zip`.
- Running `git add` on `chunks/`, `audio_slices/`, or `frames/`.

**If any red flag occurs: Do not move directory. Inspect source files first.**
