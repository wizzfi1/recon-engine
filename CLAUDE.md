# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

A financial reconciliation engine that matches transactions between two accounting systems — **PASTEL** and **IX TRAC** — by reading a single Excel file containing both sheets, performing intelligent netting and matching, and writing a multi-sheet Excel report.

## Running the Project

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Desktop GUI (primary interface):**
```bash
python ui_app.py
```

**Web server (FastAPI):**
```bash
uvicorn app.main:app --reload
```
Runs at http://localhost:8000. Endpoints: `POST /api/upload`, `POST /api/reconcile`, `GET /health`.

**Build standalone .exe:**
```bash
pip install pyinstaller
pyinstaller ReconEngine.spec
```

**Docker:**
```bash
docker build -t recon-engine .
docker run -p 8000:8000 recon-engine
```

**Tests:**
```bash
python test.py
```
Minimal — only tests the `text_match` utility. Most testing is manual with real Excel files.

## Architecture

There are **two parallel codebases** for the reconciliation logic that must be kept in sync:

| Path | Used By |
|------|---------|
| `/core/` + `/outputs/` + `/utils/` | Desktop GUI (`ui_app.py`) and CLI (`main.py`) |
| `/app/engine/` | Web API (`app/main.py`) |

The web version (`/app/engine/`) lacks progress tracking and cancellation support. The desktop version (`/core/`) is more feature-complete. When fixing bugs in the matching/netting/review logic, check **both** locations.

### Reconciliation Pipeline

The pipeline runs in this sequence, all orchestrated by `reconciler.py`:

1. **Load** (`loaders.py`) — reads the PASTEL and IXTRAC sheets from the uploaded Excel file
2. **Validate** (`validators.py`) — checks that debit/credit/amount columns are numeric
3. **Net** (`internal_netting.py`) — Stage A: exact ref+amount credit/debit pairs; Stage B: fuzzy name+amount pairs
4. **Match** (`matchers.py`) — maps PASTEL debits to IXTRAC transactions; gate requires ref match OR name score ≥ 2
5. **Review** (`reviewer.py`) — post-match recovery pass for items that weren't matched in step 4
6. **Write** (`outputs/writer.py`) — produces the multi-sheet Excel output

**Output sheets:** CONFIRMED, REF_MISMATCH, REVIEWED_MATCHES, PASTEL_OUTSTANDING, IXTRAC_OUTSTANDING, NETTED, REMAINING_CREDITS, SUMMARY.

### Key Modules

- `core/reconciler.py` — entry point `run_reconciliation()`; returns 8 items including progress/cancellation support
- `core/matchers.py` — 2-stage matching; name scoring threshold is `NAME_SCORE >= 2`
- `core/internal_netting.py` — uses `_find_column()` for robust column name resolution
- `utils/text_match.py` — token-based name scoring used throughout matching
- `core/progress.py` — `ProgressReporter` class; desktop GUI runs reconciliation in a background thread
- `config.py` — sheet names and output file path constants

### Known Issues

- **`main.py` has unresolved merge conflicts** (lines 12–41). The HEAD and master branches disagree on how many values `run_reconciliation()` returns. Do not run `main.py` without resolving this first.
- The `/app/engine/` matchers use different scoring thresholds than `/core/matchers.py` — be careful to understand which version you're modifying.
