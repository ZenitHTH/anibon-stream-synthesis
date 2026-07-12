# Anibon Database & AI Research System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a synchronized local SQLite FTS5 database for indexing Anibon streams and an AI researcher skill to query it.

**Architecture:** A core Python SQLite library, a Google Drive API sync utility, a CLI frontend for data ingestion/searching, and an Antigravity agent skill for natural language querying and cross-referencing.

**Tech Stack:** Python 3, SQLite3 (FTS5), Google API Python Client, Pytest.

## Global Constraints
- Database file is named `anibon.db`.
- FTS5 must be used for full-text search.
- Google Drive sync must use `service_account.json` and `.env`.
- Ensure no credentials or `.db` files are committed to Git.
- Fallback configuration instructions must be printed on stdout with exit code 1 if credentials are missing.

---

### Task 1: Core Database Engine (`anibon_db_core.py`)

**Files:**
- Create: `scripts/anibon_db_core.py`
- Create: `tests/test_anibon_db_core.py`

**Interfaces:**
- Consumes: JSON chunk data from `prepare_video.py` outputs.
- Produces: `init_db(db_path)`, `insert_video(db_path, metadata)`, `insert_chunks(db_path, chunks)`, `search_chunks(db_path, query, limit=5)`.

- [ ] **Step 1: Write the failing test for DB initialization and FTS search**
```python
# tests/test_anibon_db_core.py
import os
import tempfile
import pytest
from scripts.anibon_db_core import init_db, insert_video, insert_chunks, search_chunks

def test_db_init_and_search():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "anibon.db")
        init_db(db_path)
        
        insert_video(db_path, {
            "video_id": "test1234567",
            "title": "Test Stream",
            "publish_date": "2026-07-11",
            "duration_seconds": 3600
        })
        
        chunks = [{
            "chunk_id": "test1234567_0",
            "video_id": "test1234567",
            "chunk_index": 0,
            "start_sec": 0,
            "end_sec": 300,
            "start_timestamp": "00:00:00",
            "end_timestamp": "00:05:00",
            "content": "Boat says wuthering waves is cool."
        }]
        insert_chunks(db_path, chunks)
        
        results = search_chunks(db_path, "wuthering waves")
        assert len(results) == 1
        assert results[0]["video_id"] == "test1234567"
        assert "wuthering waves" in results[0]["content"]
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_anibon_db_core.py -v`
Expected: FAIL with "ModuleNotFoundError" or "ImportError"

- [ ] **Step 3: Write minimal implementation**
```python
# scripts/anibon_db_core.py
import sqlite3
import os

def init_db(db_path: str):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS videos (
        video_id TEXT PRIMARY KEY, title TEXT, publish_date TEXT, duration_seconds INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS chunks (
        chunk_id TEXT PRIMARY KEY, video_id TEXT, chunk_index INTEGER, 
        start_sec REAL, end_sec REAL, start_timestamp TEXT, end_timestamp TEXT, content TEXT,
        FOREIGN KEY(video_id) REFERENCES videos(video_id) ON DELETE CASCADE
    )''')
    c.execute('''CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
        chunk_id UNINDEXED, content, content='chunks', content_rowid='rowid'
    )''')
    conn.commit()
    conn.close()

def insert_video(db_path: str, metadata: dict):
    conn = sqlite3.connect(db_path)
    conn.execute('''INSERT OR REPLACE INTO videos 
        (video_id, title, publish_date, duration_seconds) 
        VALUES (?, ?, ?, ?)''', 
        (metadata['video_id'], metadata['title'], metadata['publish_date'], metadata['duration_seconds']))
    conn.commit()
    conn.close()

def insert_chunks(db_path: str, chunks: list):
    conn = sqlite3.connect(db_path)
    for ch in chunks:
        conn.execute('''INSERT OR REPLACE INTO chunks 
            (chunk_id, video_id, chunk_index, start_sec, end_sec, start_timestamp, end_timestamp, content)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (ch['chunk_id'], ch['video_id'], ch['chunk_index'], ch['start_sec'], ch['end_sec'], 
             ch['start_timestamp'], ch['end_timestamp'], ch['content']))
        
        # Manually maintain FTS table due to external content mapping
        conn.execute('''INSERT OR REPLACE INTO chunks_fts (rowid, chunk_id, content) 
            VALUES (last_insert_rowid(), ?, ?)''', (ch['chunk_id'], ch['content']))
    conn.commit()
    conn.close()

def search_chunks(db_path: str, query: str, limit: int = 5):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # Match using FTS5 and join with videos
    c.execute('''
        SELECT c.*, v.title FROM chunks_fts f
        JOIN chunks c ON f.chunk_id = c.chunk_id
        JOIN videos v ON c.video_id = v.video_id
        WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?
    ''', (query, limit))
    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results
```

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_anibon_db_core.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add scripts/anibon_db_core.py tests/test_anibon_db_core.py
git commit -m "feat: implement sqlite fts5 database core"
```

---

### Task 2: Google Drive API Sync Utility (`gdrive_sync.py`)

**Files:**
- Create: `scripts/gdrive_sync.py`
- Create: `tests/test_gdrive_sync.py`

**Interfaces:**
- Consumes: `.env` variables (`ANIBON_GDRIVE_FILE_ID`) and `service_account.json`.
- Produces: `verify_setup()`, `pull_database(db_path)`, `push_database(db_path)`.

- [ ] **Step 1: Write the failing test with mocks**
```python
# tests/test_gdrive_sync.py
import pytest
from unittest.mock import patch, MagicMock
from scripts.gdrive_sync import verify_setup, pull_database, push_database

@patch('scripts.gdrive_sync.os.path.exists')
def test_verify_setup_missing(mock_exists):
    mock_exists.return_value = False
    with pytest.raises(SystemExit) as e:
        verify_setup()
    assert e.value.code == 1

@patch('scripts.gdrive_sync.get_drive_service')
@patch('scripts.gdrive_sync.MediaIoBaseDownload')
@patch('scripts.gdrive_sync.verify_setup')
def test_pull_database(mock_verify, mock_download, mock_service):
    mock_svc = MagicMock()
    mock_service.return_value = mock_svc
    mock_svc.files().get_media.return_value = MagicMock()
    
    dl_instance = MagicMock()
    mock_download.return_value = dl_instance
    status_mock = MagicMock()
    status_mock.progress.return_value = 1.0
    dl_instance.next_chunk.return_value = (status_mock, True)
    
    with patch('builtins.open', unittest.mock.mock_open()):
        pull_database("dummy.db")
    
    mock_svc.files().get_media.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_gdrive_sync.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**
```python
# scripts/gdrive_sync.py
import os
import sys
import io
import dotenv

dotenv.load_dotenv()

def verify_setup():
    creds_path = os.path.join(os.path.dirname(__file__), "..", "service_account.json")
    file_id = os.environ.get("ANIBON_GDRIVE_FILE_ID")
    
    if not os.path.exists(creds_path) or not file_id:
        print("⚠️  Sync Configuration Missing: 'service_account.json' or 'ANIBON_GDRIVE_FILE_ID' not found.")
        print("Please follow these steps to configure Google Drive Sync:")
        print("1. Go to Google Cloud Console and create a project.")
        print("2. Enable the Google Drive API.")
        print("3. Create a Service Account and download the JSON key as 'service_account.json'.")
        print("4. Share your Google Drive folder with the service account email.")
        print("5. Set ANIBON_GDRIVE_FILE_ID in your .env file.")
        
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        if not os.path.exists(env_path):
            with open(env_path, "w") as f:
                f.write("ANIBON_GDRIVE_FILE_ID=your_uploaded_file_id_here\nANIBON_DB_PATH=anibon.db\n")
            print("\nGenerated template .env file. Please edit it.")
        sys.exit(1)

def get_drive_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds_path = os.path.join(os.path.dirname(__file__), "..", "service_account.json")
    creds = service_account.Credentials.from_service_account_file(
        creds_path, scopes=['https://www.googleapis.com/auth/drive']
    )
    return build('drive', 'v3', credentials=creds)

def pull_database(db_path: str):
    verify_setup()
    from googleapiclient.http import MediaIoBaseDownload
    service = get_drive_service()
    request = service.files().get_media(fileId=os.environ.get("ANIBON_GDRIVE_FILE_ID"))
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    with open(db_path, 'wb') as f:
        f.write(fh.getvalue())
    print("Database pulled successfully.")

def push_database(db_path: str):
    verify_setup()
    from googleapiclient.http import MediaFileUpload
    service = get_drive_service()
    media = MediaFileUpload(db_path, mimetype='application/x-sqlite3', resumable=True)
    service.files().update(fileId=os.environ.get("ANIBON_GDRIVE_FILE_ID"), media_body=media).execute()
    print("Database pushed successfully.")
```

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_gdrive_sync.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add scripts/gdrive_sync.py tests/test_gdrive_sync.py
git commit -m "feat: implement google drive api sync"
```

---

### Task 3: CLI Manager (`manage_anibon_db.py`) & Environment Security

**Files:**
- Create: `scripts/manage_anibon_db.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: CLI args `--pull`, `--push`, `--search`, `--import-workspaces`.
- Produces: JSON stdout for search, coordinates `gdrive_sync.py` and `anibon_db_core.py`.

- [ ] **Step 1: Secure `.gitignore`**
Append to `.gitignore`:
```gitignore
# Google API Keys & Tokens
service_account.json
credentials.json
token.json
.env

# Database file
anibon.db
```

- [ ] **Step 2: Implement CLI manager**
```python
# scripts/manage_anibon_db.py
import argparse
import os
import json
import dotenv
from anibon_db_core import init_db, search_chunks
from gdrive_sync import pull_database, push_database

dotenv.load_dotenv()
DB_PATH = os.environ.get("ANIBON_DB_PATH", "anibon.db")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pull", action="store_true")
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--search", type=str)
    args = parser.parse_args()

    if not os.path.exists(DB_PATH) and not args.pull:
        init_db(DB_PATH)

    if args.pull:
        pull_database(DB_PATH)
    elif args.push:
        push_database(DB_PATH)
    elif args.search:
        results = search_chunks(DB_PATH, args.search)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        
if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run sanity test**
Run: `python3 scripts/manage_anibon_db.py --search "test"`
Expected: Clean exit (empty JSON list `[]` output)

- [ ] **Step 4: Commit**
```bash
git add scripts/manage_anibon_db.py .gitignore
git commit -m "feat: add manage_anibon_db cli and secure gitignore"
```

---

### Task 4: AI Researcher Skill & Timestamper Integration

**Files:**
- Create: `skills/anibon-researcher/SKILL.md`
- Modify: `skills/anibon-timestamper/SKILL.md`

**Interfaces:**
- Consumes: `manage_anibon_db.py --search`.
- Produces: Agent instructions for researching and outputting answers.

- [ ] **Step 1: Create `anibon-researcher` skill**
```markdown
# skills/anibon-researcher/SKILL.md
---
name: anibon-researcher
description: Research past Anibon streams and output answers using the synchronized database.
---

# Anibon AI Researcher

When asked to research an Anibon topic or quote:

1. **Pull the latest database:**
   Run `python3 scripts/manage_anibon_db.py --pull`. If it fails with exit code 1, instruct the user to follow the setup guide printed in the terminal.
2. **Search the database:**
   Run `python3 scripts/manage_anibon_db.py --search "YOUR_QUERY_HERE"`.
3. **Read the results:**
   The output is a JSON list of matching chunks.
4. **Safety Check:**
   Apply `masking-royal-news` logic. Do not output raw sensitive political figures.
5. **Output:**
   Synthesize the answer and include direct YouTube links with timestamps: `[MM:SS](https://youtu.be/VIDEO_ID?t=SECONDS)`.
```

- [ ] **Step 2: Update `anibon-timestamper` skill**
Add the cross-reference rule to `skills/anibon-timestamper/SKILL.md`:
```markdown
### Database Cross-Referencing
When processing a new stream, if Boat explicitly references an older stream (e.g. "Like I said last year about X"):
1. Search the historical database: `python3 scripts/manage_anibon_db.py --search "X"`.
2. Extract the matching video and timestamp.
3. Append a cross-reference bullet to your output: `* Boat references his discussion on X [01:23:45 of Video ABC](https://youtu.be/ABC?t=5025)`.
```

- [ ] **Step 3: Commit**
```bash
git add skills/anibon-researcher/SKILL.md skills/anibon-timestamper/SKILL.md
git commit -m "feat: add researcher skill and timestamper db integration"
```
