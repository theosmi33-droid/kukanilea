# KUKANILEA Tool Mapping

This document maps the abstract capabilities of the Agent Fleet to concrete Python functions in the core.

| Tool Name | Worker | Python Entrypoint | Description | Confirm-Gate |
|-----------|--------|-------------------|-------------|--------------|
| `search_internet` | W05 | `app.agents.search.tavily_search` | Führt eine Web-Recherche via Tavily API durch. | False |
| `send_email` | W06 | `app.agents.mail.send_email` | Versendet eine E-Mail über SMTP. | **True** |
| `delete_file` | W10 | `app.core.logic.delete_document` | Löscht ein Dokument unwiderruflich. | **True** |
| `extract_text` | W02 | `app.core.logic._extract_text` | Liest Text aus PDFs, Office, etc. | False |
| `run_ocr` | W01 | `app.autonomy.ocr.process` | Führt Tesseract/Ollama Vision auf Bildern aus. | False |
| `query_db` | W04 | `app.core.logic.search_documents` | Durchsucht die lokale SQLite RAG/FTS Index DB. | False |
| `track_time` | W07 | `app.core.logic.time_entry_start` | Startet eine neue Stoppuhr für ein Projekt. | False |

**Tool Execution Protocol:**
- Jedes Tool, das `Confirm-Gate = True` hat, darf niemals autonom ausgeführt werden. Das System muss via `ui.require_confirmation(action)` den User-Loop triggern.
