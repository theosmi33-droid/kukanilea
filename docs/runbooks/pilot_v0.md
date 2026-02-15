# Pilot v0 - OCR (Bild-OCR) - 14-Tage-Runbook

**Ziel:** Validieren, dass OCR fuer Alltagsdokumente (Scans/Fotos) brauchbar ist und keine unerwarteten Sicherheits-/Qualitaetsprobleme auftreten. Die Ergebnisse entscheiden ueber Go/No-Go fuer PDF-OCR (Phase 2c).

## 1. Pilot-Setup (vor Start)

- **Merge & Smoke-Tests** des OCR-v0-PRs (Checkliste im PR).
- **Tenants aktivieren**: Fuer jeden Pilot-Tenant `allow_ocr = 1` setzen (Admin-UI oder direkt per SQL).
- **Testpaket bereitstellen** (10-20 Dateien pro Tenant):
  - 6 "gute" Scans/Fotos (de/en gemischt)
  - 3 "schlechte" (schief, Schatten, low-res)
  - 1 Oversize (> `AUTONOMY_OCR_MAX_BYTES`) -> erwartet `too_large`
  - 1 PDF -> erwartet `pdf_not_supported` (Ingest darf nicht abbrechen)
  - **1 Bild mit bewussten PII-Patterns**, z.B. `pilot+pii@example.com` und `+49 151 23456789` - zur Redaction-Verifikation

## 2. Betrieb (2 Wochen)

- **Taeglicher Check**: Health-Dashboard (OCR-Jobs, Fehlercodes, Dauer) via `/autonomy/health`.
- **2x woechentliches Review** (20-30 min) mit Piloten: Probleme, Workarounds, Eindruecke.
- **PII-Redaction verifizieren** (nach dem ersten Upload):
  - Suche in der Knowledge-Base nach den PII-Patterns (`pilot+pii@example.com`, `+49 151 23456789`).
  - **Erwartet:** 0 Treffer. Falls Treffer > 0 -> **Critical**, Pilot sofort stoppen.
- **Bug-Triage** nach Kategorien (siehe Abschnitt 5).

## 3. Auswertung nach 14 Tagen

Fuehre folgende SQL-Abfragen auf der Live-DB aus (oder anonymisiertem Dump).

### a) Status- und Fehlerverteilung

```sql
-- Status pro Tenant (letzte 14 Tage)
SELECT tenant_id, status, COUNT(*) AS n
FROM autonomy_ocr_jobs
WHERE created_at >= datetime('now', '-14 days')
GROUP BY tenant_id, status
ORDER BY tenant_id, status;

-- Fehlercodes pro Tenant (letzte 14 Tage)
SELECT tenant_id, COALESCE(error_code, '(none)') AS error_code, COUNT(*) AS n
FROM autonomy_ocr_jobs
WHERE created_at >= datetime('now', '-14 days')
GROUP BY tenant_id, error_code
ORDER BY tenant_id, n DESC;
```

### b) Dauer (Median & P95)

```sql
-- Median duration_ms (nur 'done'-Jobs)
WITH jobs AS (
  SELECT duration_ms
  FROM autonomy_ocr_jobs
  WHERE tenant_id = ? AND status = 'done' AND duration_ms > 0
  ORDER BY duration_ms
),
cnt AS (SELECT COUNT(*) AS n FROM jobs)
SELECT duration_ms AS median_ms
FROM jobs
LIMIT 1 OFFSET (SELECT (n - 1) / 2 FROM cnt);

-- P95 duration_ms
WITH jobs AS (
  SELECT duration_ms
  FROM autonomy_ocr_jobs
  WHERE tenant_id = ? AND status = 'done' AND duration_ms > 0
  ORDER BY duration_ms
),
cnt AS (SELECT COUNT(*) AS n FROM jobs),
idx AS (SELECT CAST((n - 1) * 0.95 AS INT) AS k FROM cnt)
SELECT duration_ms AS p95_ms
FROM jobs
LIMIT 1 OFFSET (SELECT k FROM idx);
```

### c) Ausgabequalitaet (Naehe an `max_chars`)

```sql
-- chars_out Verteilung
SELECT
  MIN(chars_out) AS min_chars,
  AVG(chars_out) AS avg_chars,
  MAX(chars_out) AS max_chars
FROM autonomy_ocr_jobs
WHERE tenant_id = ? AND status = 'done';

-- Anzahl Jobs nahe am Limit (z.B. >= 190.000 von 200.000)
SELECT COUNT(*) AS near_max
FROM autonomy_ocr_jobs
WHERE tenant_id = ? AND status = 'done' AND chars_out >= 190000;
```

## 4. Feedback-Formular (an Piloten, 5 Minuten)

1. Welche drei Dokumenttypen waren am wichtigsten?
2. Wie oft hast du per Suche etwas gefunden, das vorher nicht ging? (nie / selten / oft / sehr oft)
3. Trefferqualitaet: 1-5 (1 = unbrauchbar, 5 = perfekt)
4. OCR-Genauigkeit: 1-5
5. Geschwindigkeit ("fuehlt sich an"): schnell / ok / langsam
6. Gab es Scans, die komplett scheiterten? Welche Art?
7. Gab es falsche Treffer (Noise)? (nie / selten / oft)
8. Wurden sensible Daten korrekt versteckt (Redaction wirkt)? (ja / nein / unsicher)
9. Welche eine Verbesserung bringt dir am meisten Nutzen?
10. Wuerdest du das System nach dem Pilot weiter nutzen? (ja / nein / unter Bedingungen)

## 5. Bug-Triage (entscheidungsrelevant)

**Critical (Stop/Patch sofort)**
- PII im Eventlog oder unredactierter OCR-Text persistiert
- Tenant-Leak (falscher Tenant sieht Daten)
- READ_ONLY umgehbar
- Autonomy-Ingest bricht wegen OCR (statt best-effort)

**Major (Pilot kann weiterlaufen, aber Fix vor breitem Rollout)**
- Haeufige Timeouts bei normalen Bildern
- Tesseract-Binary fehlt oder Allowlist-Probleme in Zielumgebung
- OCR erzeugt ueberwiegend unbrauchbaren Text (Noise)

## 6. Go/No-Go-Entscheidung

**Go**, wenn **alle** folgenden Kriterien erfuellt sind:
- 0 Criticals
- Echte OCR-Fehler (exkl. `policy_denied`, `too_large`, `pdf_not_supported`) < 5-10 % aller Jobs
- Performance: P95-Dauer < 30 s (bei Standardbildern)
- Nutzen: mindestens 2/3 der Piloten bestaetigen messbare Zeitersparnis durch Suche in Scans (Fragen 2 + 10)

**No-Go**:
- Probleme analysieren und ggf. in Phase 2b (Tags/Metadaten) oder 2c (PDF-OCR) einfliessen lassen.
- OCR-Policy fuer alle deaktivieren, bis die Ursachen behoben sind.
