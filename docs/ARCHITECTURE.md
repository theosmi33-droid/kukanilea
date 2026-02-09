# Architecture Overview

## Components
- **Web**: Flask app in `app/` (UI + API).
- **Core**: `kukanilea_core_v3_fixed.py` (DB, ingest, indexing).
- **New package layout**: `kukanilea/` for domain/services/infra/web/cli.

## Dataflow (target)
Ingest → Extract → Enrich → Index → Archive.

## Storage
- SQLite DB for metadata.
- Filesystem for documents.
