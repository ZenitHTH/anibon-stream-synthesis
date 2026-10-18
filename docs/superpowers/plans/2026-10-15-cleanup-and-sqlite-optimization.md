# Barcode Fix, Repo Cleanup & SQLite Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate external barcode/PDF runtime dependencies (`No module named 'barcode'`), remove 2,064 lines of dead files/duplication across root, `packaging/`, `core/`, and `apps/`, and optimize the three SQLite bottlenecks in student search, snapshot sync, and catalog lookup.

**Architecture:** Replace third-party `python-barcode`/`Pillow`/`reportlab` calls in `core/library/services/label_service.py` with a pure-stdlib ISO/IEC 15417 Code128-B + PDF 1.4 vector generator and fix QML/adapter barcode argument bindings. Delete superseded root design docs, unused `*_windows.spec` files, and zero-import modules, centralizing `_sanitize_for_qml` and `normalize_file_path` in `core/shared/mock_qt.py`. Replace correlated per-row SQLite subqueries and Python row-by-row loops in `student_repo.py`, `apply.py`, and `book_copies` with single-pass joins, `executemany`, and a composite `(book_id, status)` index.

**Tech Stack:** Python 3.10–3.15 (stdlib `sqlite3`, `urllib.parse`), PySide6 (Qt Quick / QML), SQLite3 with FTS5 `trigram`, pytest.

**Spec:** `wiki/index.md`, `doc/book_barcode_generation.md`, `doc/student_search_algorithm.md`, `doc/database_layer_design.md`

## Global Constraints

- **Python & Dependencies:** Python >= 3.10 stdlib first (`ponytail` ladder); zero new third-party packages added to `requirements.txt`.
- **Service Return Contract:** Use `Result[T, E]`, `Ok`, and `Err` from `core.shared.result`; never raise unhandled exceptions across service or adapter boundaries (`AGENTS.md` §3.1).
- **QML Sanitization:** Always run database dictionaries through `_sanitize_for_qml` before serializing to JSON for QML (`AGENTS.md` §3.2), converting `None` to `0` for `NUMERIC_KEYS` and `""` for text keys while preserving `bool`.
- **Barcode Format & Sequence Invariant:** Format `{BARCODE_PREFIX}-{book_id:05d}-{copy_seq:02d}` (`BARCODE_PREFIX = "SMTE"`), where `copy_seq` is `count_copies_ever(conn, book_id) + 1` and never reuses retired or disposed sequence numbers (`doc/book_barcode_generation.md` §2–§3).
- **Search Privacy Invariant:** `student_repo.search_students` must never match `national_id` (`doc/student_search_algorithm.md`).
- **Wiki Maintenance:** Update relevant `wiki/` pages and append a summary entry to `wiki/log.md` (`AGENTS.md` §4).

## Review Focus

1. **Barcode strings containing PDF delimiters `(`, `)`, `\` or non-ASCII characters in `export_label_sheet_pdf`:** PDF text stream must escape `\`, `(`, `)` and Code128-B encoder must map out-of-range characters (`ord(ch) < 32` or `ord(ch) > 126`) to `?` without raising `IndexError` or producing a corrupt PDF.
2. **Stale imports or re-creation of deleted dead modules (`core/library/models.py`, `core/shared/errors.py`, `packaging/*_windows.spec`, duplicate root `.md` files):** Codebase must have zero references to deleted files while keeping `core.student.models` intact.
3. **Percent-encoded Thai `file://` URLs and boolean values in shared adapter utilities:** `normalize_file_path("file:///tmp/%E0%B8%99%E0%B8%A3.xlsx")` must decode to `"/tmp/นร.xlsx"`, and `_sanitize_for_qml({"ok": True, "student_id": None})` must keep `True` as `bool` (not `1`) even though `isinstance(True, int)` is `True` in Python.
4. **Student search with embedded double quotes (`สม"ชาย`) or historical enrollments from prior semesters:** FTS5 query construction must escape `"` as `""` without raising `sqlite3.OperationalError`, and room/grade filters must match only each student's latest enrollment (`MAX(id)`), never an older semester's room.
5. **Chained student ID renumbering (`1001 -> 8001 -> 9001`) during batch `apply_sync` with active library loans:** `student_id_changes` must apply in chronological `id ASC` order before `executemany` upserts so `ON UPDATE CASCADE` preserves `loans.student_id` without `FOREIGN KEY constraint failed`.

---

### Task 1: Pure-Stdlib Code128 PDF Label Generator & Barcode Lookup

**Files:**
- Modify: `core/library/services/label_service.py`
- Modify: `apps/librarian_management_app/adapters/librarian_admin_adapter.py:137-220`
- Modify: `apps/librarian_management_app/qml/views/BarcodeGeneratorView.qml:110-140`
- Modify: `apps/librarian_management_app/qml/dialogs/BookActionDialogs.qml:120-190`
- Modify: `data/repositories/book_repo.py:235-265`
- Modify: `apps/booth_app/main.py:20-35`
- Test: `tests/test_barcode_and_disposed.py`

**Interfaces:**
- Consumes: `core.library.policy.BARCODE_PREFIX` (`"SMTE"`), `data.paths.get_default_db_path(app_name: str, db_filename: str) -> Path`
- Produces:
  - `export_label_sheet_pdf(copies: List[Union[Tuple[int, str], str]], output_path: str, cols: int = 3, rows: int = 8) -> None` in `core/library/services/label_service.py`
  - `LibrarianAdminAdapter.addBook(title, isbn="", author="", publisher="", category_id="", shelf_location="", barcodes_csv="") -> str` (defaults blank `barcodes_csv` to `copy_count = 1`)
  - `LibrarianAdminAdapter.addCopies(book_id: int, copies_or_barcodes: Any = "1") -> str` (accepts `int` or `str`)
  - `book_repo.get_copy_by_barcode(conn: sqlite3.Connection, barcode: str) -> Optional[sqlite3.Row]` (case/dash-insensitive + ISBN fallback)

- [x] **Step 1: Write the failing tests in `tests/test_barcode_and_disposed.py`**

```python
def test_librarian_admin_adapter_barcodes_and_pdf(conn, tmp_path):
    adapter = LibrarianAdminAdapter(conn)
    output_pdf = str(tmp_path / "adapter_labels.pdf")

    add_resp = json.loads(adapter.addBook(
        title="ชีววิทยา ม.1", isbn="9780123456789", author="ดร. สมปอง", barcodes_csv="2"
    ))
    assert add_resp["ok"]
    book_id = add_resp["data"]["book_id"]
    barcodes = add_resp["data"]["barcodes"]
    assert barcodes == [f"SMTE-{book_id:05d}-01", f"SMTE-{book_id:05d}-02"]

    add_copies_resp = json.loads(adapter.addCopies(book_id, "1"))
    assert add_copies_resp["ok"]
    assert add_copies_resp["data"]["barcodes"] == [f"SMTE-{book_id:05d}-03"]

    all_barcodes = barcodes + add_copies_resp["data"]["barcodes"]
    pdf_resp = json.loads(adapter.exportLabelsPdf(json.dumps(all_barcodes), output_pdf))
    assert pdf_resp["ok"]
    assert os.path.exists(output_pdf)
    assert os.path.getsize(output_pdf) > 1000

    # Blank barcodes_csv defaults to 1 copy; int addCopies; case/dash/ISBN lookup
    default_book = json.loads(adapter.addBook(title="เคมี ม.4", isbn="978-616-999", barcodes_csv=""))
    assert default_book["ok"]
    b2_id = default_book["data"]["book_id"]
    assert default_book["data"]["barcodes"] == [f"SMTE-{b2_id:05d}-01"]

    int_copies = json.loads(adapter.addCopies(b2_id, 2))
    assert int_copies["ok"]
    assert int_copies["data"]["barcodes"] == [f"SMTE-{b2_id:05d}-02", f"SMTE-{b2_id:05d}-03"]

    assert json.loads(adapter.getCopyByBarcode(f"smte-{b2_id:05d}-01"))["ok"]
    assert json.loads(adapter.getCopyByBarcode(f"SMTE{b2_id:05d}02"))["ok"]
    assert json.loads(adapter.getCopyByBarcode("978-616-999"))["ok"]


def test_export_label_sheet_pdf_escapes_special_and_non_ascii_chars(tmp_path):
    output_pdf = str(tmp_path / "special_labels.pdf")
    export_label_sheet_pdf(["SMTE-(01)\\A", "SMTE-ไทย-02"], output_pdf)
    with open(output_pdf, "rb") as f:
        raw = f.read()
    assert raw.startswith(b"%PDF-1.4")
    assert b"SMTE-\\(01\\)\\\\A" in raw
```

- [ ] **Step 2: Run test to verify it passes with stdlib PDF generator**

Run: `pytest tests/test_barcode_and_disposed.py -v`
Expected: PASS (5+ passed, zero `ModuleNotFoundError: No module named 'barcode'`).

- [x] **Step 3: Implement stdlib `export_label_sheet_pdf` in `core/library/services/label_service.py` and fix QML/adapter/repo bindings**

Encode Code128-B bars via `_CODE128_PATTERNS` (`0..106`, start code `104`, modulo-103 checksum, stop `106`) and emit PDF 1.4 vector rectangles (`re f`) + dashed cut guides (`[3 3] 0 d`) + `/Helvetica-Bold` text. Fix `BarcodeGeneratorView.qml` line 113 argument order `(title, isbn, author, "", catId, shelf, count.toString())` and line 135 `count.toString()`.

- [x] **Step 4: Commit**

```bash
git add core/library/services/label_service.py apps/ data/repositories/book_repo.py tests/test_barcode_and_disposed.py wiki/
git commit -m "fix(library): use stdlib barcode PDF and fix lookup"
```

---

### Task 2: Dead File, Duplicate Doc & Unused Spec Removal (`ponytail-audit`)

**Files:**
- Delete: `application_layer_design.md`
- Delete: `database_layer_design.md`
- Delete: `design_doc.md`
- Delete: `ui_layer_design.md`
- Delete: `query_lm_studio.py`
- Delete: `seed_sample_students.py`
- Delete: `packaging/booth_app_windows.spec`
- Delete: `packaging/librarian_management_windows.spec`
- Delete: `packaging/student_management_windows.spec`
- Delete: `core/library/models.py`
- Delete: `core/shared/errors.py`
- Modify: `tests/test_spec_exclusions.py`

**Interfaces:**
- Consumes: `os.path` in `tests/test_spec_exclusions.py`
- Produces: Clean repo tree (`-2,014 lines`) with canonical docs in `doc/` and `wiki/`, canonical specs in `packaging/{librarian_management,student_management,booth_app}.spec`, and canonical error/result handling in `core/shared/result.py`.

- [ ] **Step 1: Write the failing test in `tests/test_spec_exclusions.py`**

```python
def test_dead_files_and_duplicate_docs_removed():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    removed_paths = [
        "application_layer_design.md",
        "database_layer_design.md",
        "design_doc.md",
        "ui_layer_design.md",
        "query_lm_studio.py",
        "seed_sample_students.py",
        "packaging/booth_app_windows.spec",
        "packaging/librarian_management_windows.spec",
        "packaging/student_management_windows.spec",
        "core/library/models.py",
        "core/shared/errors.py",
    ]
    for rel in removed_paths:
        assert not os.path.exists(os.path.join(repo_root, rel)), f"Dead file still exists: {rel}"

    # Canonical files must remain
    for kept in [
        "doc/design_doc.md",
        "wiki/index.md",
        "packaging/librarian_management.spec",
        "packaging/student_management.spec",
        "packaging/booth_app.spec",
        "core/student/models.py",
        "core/shared/result.py",
    ]:
        assert os.path.exists(os.path.join(repo_root, kept)), f"Required file missing: {kept}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_spec_exclusions.py::test_dead_files_and_duplicate_docs_removed -v`
Expected: FAIL with `"Dead file still exists: application_layer_design.md"`

- [ ] **Step 3: Delete the 11 dead/duplicate files**

Remove the 4 duplicate root markdown files, 2 unused root scripts, 3 unused `packaging/*_windows.spec` files, `core/library/models.py`, and `core/shared/errors.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_spec_exclusions.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: remove duplicate docs, unused specs, and dead modules"
```

---

### Task 3: Shared QML Sanitizer & `file://` URL Normalizer

**Files:**
- Modify: `core/shared/mock_qt.py`
- Modify: `apps/student_management_app/adapters/student_admin_adapter.py:1-55`
- Modify: `apps/librarian_management_app/adapters/librarian_admin_adapter.py:1-40`
- Modify: `apps/booth_app/adapters/booth_adapter.py:1-35`
- Test: `tests/test_adapters.py`

**Interfaces:**
- Consumes: `urllib.parse.unquote`, `urllib.parse.urlparse`, `typing.Any`, `typing.Set`
- Produces:
  - `NUMERIC_KEYS: Set[str]` in `core/shared/mock_qt.py`
  - `_sanitize_for_qml(obj: Any) -> Any` in `core/shared/mock_qt.py` (re-exported in adapters for backward compatibility with existing test imports)
  - `normalize_file_path(file_path: str) -> str` in `core/shared/mock_qt.py`

- [ ] **Step 1: Write the failing test in `tests/test_adapters.py`**

```python
def test_normalize_file_path_thai_url_and_sanitize_preserves_bool():
    from core.shared.mock_qt import _sanitize_for_qml, normalize_file_path

    assert normalize_file_path("file:///tmp/%E0%B8%99%E0%B8%A3.xlsx") == "/tmp/นร.xlsx"
    assert normalize_file_path("/tmp/plain.sqlite") == "/tmp/plain.sqlite"

    sanitized = _sanitize_for_qml([{"student_id": None, "active": True, "full_name": None}])
    assert sanitized[0]["student_id"] == 0
    assert sanitized[0]["active"] is True
    assert sanitized[0]["full_name"] == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_adapters.py::test_normalize_file_path_thai_url_and_sanitize_preserves_bool -v`
Expected: FAIL with `ImportError: cannot import name '_sanitize_for_qml' from 'core.shared.mock_qt'`

- [ ] **Step 3: Implement `NUMERIC_KEYS`, `_sanitize_for_qml(obj: Any) -> Any`, and `normalize_file_path(file_path: str) -> str` in `core/shared/mock_qt.py` and import in all 3 adapters**

In `core/shared/mock_qt.py`, define the union `NUMERIC_KEYS` set (`student_id`, `academic_year`, `semester`, `room`, `seq_no`, `total_copies`, `available_copies`, `book_id`, `copy_id`, `loan_id`, `fine_id`, `reservation_id`, `old_id`, `new_id`, `category_id`), `_sanitize_for_qml`, and `normalize_file_path`. Import them in `student_admin_adapter.py`, `librarian_admin_adapter.py`, and `booth_adapter.py`, replacing duplicate definitions and inline `file://` parsing blocks.

- [ ] **Step 4: Run adapter tests to verify they pass**

Run: `pytest tests/test_adapters.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/shared/mock_qt.py apps/ tests/test_adapters.py
git commit -m "refactor(adapters): centralize QML sanitizer and file URL normalizer"
```

---

### Task 4: Student Search Single-Pass Enrollment & FTS5 Join

**Files:**
- Modify: `data/repositories/student_repo.py:7-160`
- Test: `tests/test_search_algorithm.py`

**Interfaces:**
- Consumes: `students`, `enrollments`, `students_fts` tables in SQLite
- Produces:
  - `search_students(conn, query, grade_level=None, room=None, status=None, limit=50, offset=0) -> List[sqlite3.Row]`
  - `count_students(conn, query, grade_level=None, room=None, status=None) -> int`
  - `get_student(conn, student_id: int) -> Optional[sqlite3.Row]`

- [ ] **Step 1: Write the failing/edge-case test in `tests/test_search_algorithm.py`**

```python
def test_search_students_ignores_past_enrollment_and_escapes_quotes(conn):
    from data.repositories import student_repo

    conn.execute(
        "INSERT INTO students (student_id, full_name, status) VALUES (4001, 'เด็กชายสม\"ชาย ใจดี', 'active')"
    )
    conn.execute(
        "INSERT INTO enrollments (student_id, academic_year, semester, grade_level, room) "
        "VALUES (4001, 2566, 1, 'ม.1', 1), (4001, 2567, 1, 'ม.2', 2)"
    )
    conn.commit()

    # Old grade/room must not match
    assert len(student_repo.search_students(conn, query="", grade_level="ม.1", room=1)) == 0
    assert student_repo.count_students(conn, query="", grade_level="ม.1", room=1) == 0

    # Latest grade/room and embedded quote FTS5 query must match without syntax error
    rows = student_repo.search_students(conn, query='สม"ชาย', grade_level="ม.2", room=2)
    assert len(rows) == 1
    assert rows[0]["student_id"] == 4001
    assert rows[0]["grade_level"] == "ม.2"
```

- [ ] **Step 2: Run test to verify current behavior and query plan**

Run: `pytest tests/test_search_algorithm.py -v`
Expected: PASS after replacing correlated subqueries.

- [ ] **Step 3: Replace correlated `max(e2.id)` and triple `students_fts` subqueries in `data/repositories/student_repo.py`**

Use a single latest-enrollment join:
```sql
LEFT JOIN (
    SELECT student_id, MAX(id) AS max_id
    FROM enrollments
    GROUP BY student_id
) latest_e ON latest_e.student_id = s.student_id
LEFT JOIN enrollments e ON e.id = latest_e.max_id
```
And for `len(clean_query) >= 3` non-digit queries, `LEFT JOIN (SELECT rowid, rank FROM students_fts WHERE students_fts MATCH ?) fts ON fts.rowid = s.student_id` so `students_fts` is queried once instead of 3 times per row (`WHERE (fts.rowid IS NOT NULL OR s.full_name LIKE ?)` and `ORDER BY COALESCE(fts.rank, 999) ASC, s.student_id ASC`).

- [ ] **Step 4: Run search and repository test suites**

Run: `pytest tests/test_search_algorithm.py tests/test_repositories.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add data/repositories/student_repo.py tests/test_search_algorithm.py
git commit -m "perf(student_repo): replace correlated enrollment and FTS5 subqueries with single-pass joins"
```

---

### Task 5: Batch Snapshot Sync (`executemany`) & Composite Copy Status Index

**Files:**
- Create: `data/migrations/0009_copies_book_status_idx.sql`
- Modify: `data/sync/apply.py:30-95`
- Modify: `wiki/database/schema.md`
- Modify: `wiki/log.md`
- Test: `tests/test_sync_edge_cases.py`

**Interfaces:**
- Consumes: `data.migrate.apply_migrations`, `data.sync.diff.compute_diff`
- Produces:
  - Migration `0009_copies_book_status_idx.sql` creating `idx_copies_book_status ON book_copies(book_id, status)`
  - Batched `apply_sync(snapshot_path: str, local_conn: sqlite3.Connection, actor: Optional[str] = None) -> Result` using `local_cur.executemany` and `ORDER BY id ASC` on `student_id_changes`

- [ ] **Step 1: Write the failing test in `tests/test_sync_edge_cases.py`**

```python
def test_apply_sync_chained_id_renumber_preserves_loans_and_index_exists(tmp_path):
    from data.db import get_connection
    from data.migrate import apply_migrations
    from data.sync.export import export_snapshot
    from data.sync.apply import apply_sync
    from data.repositories import book_repo, loan_repo

    # Setup student DB with chained ID change: 1001 -> 8001 -> 9001
    st_conn = get_connection(str(tmp_path / "st.sqlite"), pin="123456")
    apply_migrations(st_conn)
    st_conn.execute(
        "INSERT INTO students (student_id, full_name, status) VALUES (9001, 'นายสายฟ้า ไวมาก', 'active')"
    )
    st_conn.execute(
        "INSERT INTO student_id_changes (old_id, new_id, reason, changed_at) VALUES "
        "(1001, 8001, 'step1', '2026-10-01T00:00:00Z'), "
        "(8001, 9001, 'step2', '2026-10-02T00:00:00Z')"
    )
    st_conn.commit()
    snap_path = str(tmp_path / "chained_snap.sqlite")
    export_snapshot(st_conn, snap_path)
    st_conn.close()

    # Setup library DB where student 1001 currently holds an active loan
    lib_conn = get_connection(str(tmp_path / "lib.sqlite"), pin="123456")
    apply_migrations(lib_conn)
    lib_conn.execute(
        "INSERT INTO students (student_id, full_name, status) VALUES (1001, 'นายสายฟ้า ไวมาก', 'active')"
    )
    b_id = book_repo.add_book(lib_conn, title="ฟิสิกส์อะตอม")
    c_ids = book_repo.add_copies(lib_conn, b_id, ["SMTE-00001-01"])
    loan_id = loan_repo.create_loan(
        lib_conn, copy_id=c_ids[0], student_id=1001,
        borrowed_at="2026-10-01T00:00:00Z", due_at="2026-10-15T00:00:00Z"
    )

    res = apply_sync(snap_path, lib_conn)
    assert res.ok
    loan_row = lib_conn.execute("SELECT student_id FROM loans WHERE loan_id = ?", (loan_id,)).fetchone()
    assert loan_row["student_id"] == 9001

    idx_row = lib_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_copies_book_status'"
    ).fetchone()
    assert idx_row is not None
    lib_conn.close()
```

- [ ] **Step 2: Run test to verify it fails before `0009_copies_book_status_idx.sql`**

Run: `pytest tests/test_sync_edge_cases.py::test_apply_sync_chained_id_renumber_preserves_loans_and_index_exists -v`
Expected: FAIL with `assert idx_row is not None`

- [ ] **Step 3: Create `data/migrations/0009_copies_book_status_idx.sql` and batch `data/sync/apply.py` with `executemany`**

In `data/migrations/0009_copies_book_status_idx.sql`:
```sql
CREATE INDEX IF NOT EXISTS idx_copies_book_status ON book_copies(book_id, status);
```
In `data/sync/apply.py`, query `SELECT * FROM student_id_changes ORDER BY id ASC`, and replace the `for s in students:` and `for e in enrollments:` loops with `local_cur.executemany(...)`. Update `wiki/database/schema.md` and `wiki/log.md`.

- [ ] **Step 4: Run sync and migration tests to verify they pass**

Run: `pytest tests/test_sync_edge_cases.py tests/test_migrations.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add data/migrations/0009_copies_book_status_idx.sql data/sync/apply.py tests/test_sync_edge_cases.py wiki/
git commit -m "perf(data): batch snapshot sync with executemany and index book_copies(book_id, status)"
```
