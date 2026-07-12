# Anibon Database & AI Research System — Design Spec

**Date:** 2026-07-11  
**Plugin:** `anibon-stream-synthesis`  
**Status:** Under Review

---

## Overview

A system that enables indexing, storing, and querying transcript chunks of long-form Anibon livestreams across multiple machines (up to 5 PCs) without central web-server hosting. It relies on a local SQLite database with Full-Text Search (FTS5) synchronized via the Google Drive API, and integrates a dedicated AI Researcher agent skill to answer user queries and automatically cross-reference historical streams during timestamp generation.

---

## Goals

- Maintain a central repository of all indexed Anibon stream transcript segments.
- Enable fast keyword and phrase searches across multi-hour streams using SQLite's native FTS5 index.
- Synchronize database updates across 5 different PCs using the Google Drive API directly (without requiring the Google Drive desktop app).
- Allow the `anibon-researcher` skill to retrieve matching segments and synthesize natural language answers.
- Allow the `anibon-timestamper` skill to query this database to automatically cross-reference topics mentioned by Boat from older streams.
- Ensure strict security of Google Cloud credentials and prevent database leakage.

## Non-Goals

- No multi-user concurrent write coordination (conflicts are resolved by overwriting via direct push/pull).
- No web application UI (all operations are CLI and agent-driven).
- No vector database or external search services (e.g. Algolia) to keep dependencies to standard Python libraries where possible.

---

## System Architecture & Data Flow

```
+--------------------------------------------------------+
|                      Google Drive                      |
|                  (Host: anibon.db)                     |
+--------------------------------------------------------+
                           ^
             Pull (Sync)   |   Push (Index Update)
                           v
+--------------------------------------------------------+
|                       Local PC                         |
|                                                        |
|   +-------------------+        +-------------------+   |
|   |    anibon.db      | <----> |  manage_db.py     |   |
|   |  (SQLite + FTS5)  |        |    (CLI Sync &    |   |
|   +-------------------+        |     Ingestion)    |   |
|             ^                  +-------------------+   |
|             | Query                      ^             |
|             v                            | Invoke      |
|   +-------------------+        +-------------------+   |
|   | anibon-researcher |        | anibon-timestamper|   |
|   |   (Agent Skill)   |        |   (Agent Skill)   |   |
|   +-------------------+        +-------------------+   |
+--------------------------------------------------------+
```

### Ingestion Flow
1. **Bulk Ingest:** `manage_anibon_db.py --import-workspaces` scans folders like `youtube_*_workspace/chunks/chunk_*.json` or `anibon_*_workspace/chunks/chunk_*.json` and populates the database.
2. **On-Demand Indexing:** `manage_anibon_db.py --index-video <URL_OR_ID>` invokes the existing transcript preparation pipelines to download, clean, chunk, and index a specific video.

### Query Flow (AI Researcher)
1. User asks a natural language question about a past stream.
2. The `anibon-researcher` skill pulls the latest database using the sync utility, then runs:
   ```bash
   python3 scripts/manage_anibon_db.py --search "query text"
   ```
3. The DB manager queries the FTS5 virtual table and returns a JSON list of matching chunks (limiting to top 3-5 matches).
4. The agent loads the small text content of only these chunks, applies `masking-royal-news` if risk signals are detected, and outputs a synthesized response containing direct video links with timestamp query params (e.g., `[02:10:05](https://youtu.be/VIDEO_ID?t=7805)`).

### Timestamper Cross-Reference Integration
1. During timestamping, `anibon-timestamper` (or its talk sub-skills) processes a new transcript segment.
2. If the AI detects Boat referencing an old stream/topic, it triggers a search programmatically.
3. The query returns the exact match in history, which the AI automatically appends as a note to the new timestamp list (e.g., `* Boat references his discussion on X from last year's stream [01:23:45 of Video ABC](https://youtu.be/ABC?t=5025)`).

---

## SQLite Database Schema

The database `anibon.db` consists of three tables:

### 1. `videos` (Metadata table)
- `video_id` TEXT PRIMARY KEY (11-character YouTube video ID)
- `title` TEXT (Video title)
- `publish_date` TEXT (ISO format `YYYY-MM-DD`)
- `duration_seconds` INTEGER (Total video length in seconds)

### 2. `chunks` (Relational transcript mapping table)
- `chunk_id` TEXT PRIMARY KEY (Format: `video_id_chunk_index`)
- `video_id` TEXT (Foreign key referencing `videos(video_id)` ON DELETE CASCADE)
- `chunk_index` INTEGER (Sequential index of the chunk)
- `start_sec` REAL (Start timestamp in seconds)
- `end_sec` REAL (End timestamp in seconds)
- `start_timestamp` TEXT (Start timestamp formatted as `HH:MM:SS`)
- `end_timestamp` TEXT (End timestamp formatted as `HH:MM:SS`)
- `content` TEXT (Cleaned, space-normalized transcript block text)

### 3. `chunks_fts` (FTS5 Virtual Table for Search)
An external content index table tied to the `chunks` table:
```sql
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    chunk_id UNINDEXED,
    content,
    content='chunks',
    content_rowid='rowid'
);
```
Triggers will maintain consistency between the `chunks` table and `chunks_fts` virtual table.

---

## Google Drive API Integration & Sync

To manage syncing across 5 PCs without the Google Drive desktop app, we will use a Python sync module (`scripts/gdrive_sync.py`) running on the standard `google-api-python-client`.

### Authentication
- Supported via **Service Account JSON** (`service_account.json`).
- Credentials key file is saved locally in the plugin directory.
- The shared Google Drive folder is shared with the Service Account email.

### CLI Operations
- **`--pull`**: Connects to the API, checks the remote file's modification time against the local file, and downloads it if the remote database is newer.
- **`--push`**: Uploads the local `anibon.db` file to Google Drive, overwriting the existing file using the same File ID.

---

## Security & Secret Management

To ensure credentials and databases are never pushed to public repositories on GitHub:

1. **Git Exclusions (`.gitignore`):**
   ```gitignore
   # SQLite database file
   anibon.db
   
   # Google Cloud / Google Drive Credentials
   service_account.json
   credentials.json
   token.json
   
   # Local configuration
   .env
   ```

2. **Configuration template (`.env.example`):**
   ```env
   ANIBON_GDRIVE_FILE_ID=your_google_drive_file_id_here
   ANIBON_DB_PATH=./anibon.db
   ```

3. **Runtime Credentials & Setup Check:**
   Before running `--push`, `--pull`, or `--search`, the script checks if `service_account.json` and `.env` are present.
   
   If any configuration is missing, the script will:
   - **Auto-generate a `.env` template:** If `.env` is missing, it will automatically create it with default placeholder values.
   - **Print an Interactive Console Guide:** It will intercept the error and print a clear step-by-step setup walkthrough to guide the user:
     ```text
     ⚠️  Sync Configuration Missing: 'service_account.json' not found.

     Please follow these steps to configure Google Drive Sync:
     1. Go to the Google Cloud Console: https://console.cloud.google.com/
     2. Create a new project (e.g. "Anibon Database Sync").
     3. Go to "API Library" -> Search "Google Drive API" -> Click "Enable".
     4. Go to "Credentials" -> Click "+ CREATE CREDENTIALS" -> "Service Account".
     5. Name it, click "Create", and complete the steps.
     6. Click on the newly created Service Account -> Go to "Keys" -> "Add Key" -> "Create new key" -> Choose "JSON" -> Click "Create".
     7. Save the downloaded file exactly as 'service_account.json' in this folder:
        /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/
     8. In Google Drive, share your database folder with the service account's email address.
     9. Upload your local 'anibon.db' to that folder, get its File ID, and set it in your local '.env' file:
        ANIBON_GDRIVE_FILE_ID=your_uploaded_file_id_here
     ```
   - **Exit cleanly:** The script exits with exit code `1` (indicating configuration error) instead of throwing confusing Python tracebacks.

---

## File Layout

```
skills/
  anibon-researcher/
    SKILL.md             ← new (orchestrates natural language research queries)
  anibon-timestamper/
    SKILL.md             (updated to search and cross-reference when needed)
    
scripts/
  manage_anibon_db.py    ← new (entry point for search, bulk ingest, and push/pull)
  gdrive_sync.py         ← new (contains Google Drive API download/upload logic)
  anibon_db_core.py      ← new (handles database schemas, connections, FTS5 queries)
```
