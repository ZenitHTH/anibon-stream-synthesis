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

1. **NEVER CREATE A BLANK `timestamp_workspace` — CLONE FROM GITHUB FIRST**:
   `timestamp_workspace` is an established private GitHub repository containing historical catalog metadata, 120+ stream indexes, and automation tooling. If `~/timestamp_workspace` does NOT exist locally, **NEVER** run `mkdir` to create an empty directory or `git init`. You MUST clone the private repository first:
   ```bash
   git clone https://github.com/ZenitHTH/timestamp-workspace.git ~/timestamp_workspace
   ```
   *(or `git clone git@github.com:ZenitHTH/timestamp-workspace.git ~/timestamp_workspace` if SSH is configured).*
2. **PULL LATEST BEFORE INGESTING**: Always ensure `git -C ~/timestamp_workspace pull` is run before importing new streams to prevent diverged history or merge conflicts.
3. **IMPORT FIRST, MOVE ONLY IF BACKED UP**: Never move a workspace into `youtube_workspaces/backed_up/` before `import_workspace.py` confirms successful parsing and catalog update. If import fails, DO NOT MOVE the directory.
4. **ACTIVE WORKSPACES ONLY**: Never move `.zip` archives or directories ending in `_Backup` (e.g. `youtube_W0bmqWlx4z4_workspace_Backup`). Leave them in `~`.
5. **NEVER COPY RAW MEDIA TO GIT**: Never copy whole workspaces, audio slices, or frames into `timestamp_workspace`. Only markdown summaries and catalog metadata belong in `timestamp_workspace`.

---

## Canonical Paths & Remotes

| Component | Path / Remote | Description |
|-----------|---------------|-------------|
| Master Catalog Repo | `https://github.com/ZenitHTH/timestamp-workspace.git` | Private GitHub repository |
| Local Catalog Root | `/Users/zenithth/timestamp_workspace/` | Local Git clone for index, README, and markdown stamps |
| Ingestion Script | `/Users/zenithth/timestamp_workspace/import_workspace.py` | Normalizes stamps, updates `catalog.json` & `README.md` |
| Markdown Store | `/Users/zenithth/timestamp_workspace/by_video_id/` | `timestamp_<video_id>.md` files |
| Master JSON | `/Users/zenithth/timestamp_workspace/metadata/catalog.json` | Master structured index |
| Archived Workspaces | `/Users/zenithth/youtube_workspaces/backed_up/` | Destination for raw source workspaces |

---

## Workflow (Linear, Top-to-Bottom)

### 0. Ensure `timestamp_workspace` Exists (Clone or Pull)

Before touching any workspace files, verify the local catalog exists and is synchronized:

```bash
if [ ! -d "/Users/zenithth/timestamp_workspace/.git" ]; then
  echo "timestamp_workspace not found locally. Cloning private GitHub repository..."
  git clone https://github.com/ZenitHTH/timestamp-workspace.git /Users/zenithth/timestamp_workspace
else
  git -C /Users/zenithth/timestamp_workspace pull
fi
```

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
| Creating empty `timestamp_workspace` | **FATAL**. `timestamp_workspace` is a private GitHub repo (`ZenitHTH/timestamp-workspace.git`). You MUST `git clone` it; never `mkdir` a blank repo. |
| Moving workspace before import | Violates "if doesn't backup, don't move dir". Run `import_workspace.py` first. |
| Moving `.zip` or `_Backup` folders | These must remain in `~` untouched. Filter using regex `^youtube_[A-Za-z0-9_-]+_workspace$`. |
| Private stream causes `yt-dlp` error | `import_workspace.py` falls back to `live_chat.json` timestamp to obtain broadcast date automatically. |
| Copying raw chunks into `timestamp_workspace` | Git repo bloat. Only markdown and metadata go to `timestamp_workspace`. |
| Forgetting to update `workspace_path` | Keep `metadata/catalog.json` synchronized when relocating workspaces. |

---

## Red Flags - STOP and Verify

- `timestamp_workspace` does not exist locally and you are about to run `mkdir` or `git init`. **STOP: Run `git clone https://github.com/ZenitHTH/timestamp-workspace.git ~/timestamp_workspace` instead.**
- Workspace has 0 timestamps detected.
- `by_video_id/timestamp_<video_id>.md` is 0 bytes or missing.
- Moving a folder named `*_Backup` or `*.zip`.
- Running `git add` on `chunks/`, `audio_slices/`, or `frames/`.

**If any red flag occurs: Do not move directory. Inspect source files first.**
