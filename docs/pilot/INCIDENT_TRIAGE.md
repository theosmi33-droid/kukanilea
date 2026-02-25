# KUKANILEA Pilot Incident Triage Board

Dieses Board dient der strukturierten Erfassung von Fehlern, Dumps und Feedback der Pilotkunden.

## Erfassungsschema

| Customer_ID | HW_Profile | Latency_Score | Status | Notes |
|-------------|------------|---------------|--------|-------|
| FLISA       | M2 (8C/16G)| < 200ms       | Running| Läuft stabil. OCR ok. |
| ...         | ...        | ...           | ...    | ...   |

## Diagnostic-Dumps Analyse
- **PicoClaw/OCR:** Bei Fehlern im `vision_pro` Modus Logdatei `app.jsonl` auf `ocr_failed` prüfen.
- **Voice/Whisper:** Bei Latenzen > 2s im `voice_command` Modus prüfen, ob das Modell auf CPU statt Metal/CUDA gewechselt ist.
- **SQL Locks:** Falls `OperationalError` im Dump auftaucht, `db_cache_size_mb` in `get_optimal_settings` erhöhen.
