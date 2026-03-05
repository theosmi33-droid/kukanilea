# KUKANILEA Launch Evidence Checklist

Ziel: Launch-Readiness ist nur gültig, wenn sie reproduzierbar messbar ist. Kein Prozent-Status ohne Evidence.

## Nutzung

- Vor jedem RC-Release und vor jeder Kundeninstallation ausführen.
- Ergebnis unter `docs/reviews/codex/` oder `docs/status/` ablegen.
- `GO` nur bei 7/7 PASS.

---

## Gate 0 (Schnell) — One-Command Reality Check

```bash
scripts/ops/launch_evidence_gate.sh
```

Akzeptanz:
- Ergebnis im Report ist `**GO**`.
- Keine FAIL-Gates.

Optional für schnellen Zwischenstand:

```bash
scripts/ops/launch_evidence_gate.sh --skip-healthcheck
```

Hinweis (wichtig für CI):
- Bei Log-Pipelines immer mit `pipefail` ausführen, damit Gate-Fehler nicht als false-green enden:

```bash
set -o pipefail
scripts/ops/launch_evidence_gate.sh | tee /tmp/gate.txt
```
- Exit-Code-Konvention:
  - `0` = GO/GO with Notes
  - `3` = NO-GO (mindestens ein P0-Gate ist FAIL oder kritischer Fehler)


---

## Gate 1 — Repo & GitHub Truth (CLI only)

Zweck: Widersprüche aus Web-Zählern ausschließen.

```bash
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git fetch origin --prune
git rev-parse --short HEAD
git rev-parse --short origin/main
gh pr list --repo theosmi33-droid/kukanilea --state open --json number,title,headRefName
gh run list --repo theosmi33-droid/kukanilea --branch main --limit 12 --json workflowName,displayTitle,status,conclusion
```

PASS wenn:
- `HEAD == origin/main` (für Release-Check).
- Open PRs für Release-Scope = 0.
- Main-Runs in Liste sind `completed/success`.

Evidence:
- Datum/Zeit:
- Branch/Commit:
- Open PRs:
- Main CI:
- Ergebnis: `PASS | FAIL`

---

## Gate 2 — Core-Stabilität

```bash
git status --short
./scripts/ops/healthcheck.sh
pytest -q
```

PASS wenn:
- Keine unerwarteten lokalen Änderungen für den Release-Scope.
- Healthcheck Exit-Code 0 (inkl. Security- und Contract-Gates).
- Pytest ohne Failures.

Evidence:
- Working tree:
- Healthcheck:
- Pytest:
- Ergebnis: `PASS | FAIL`

---

## Gate 3 — Offline/Zero-CDN & External Requests

```bash
python scripts/ops/verify_guardrails.py
./scripts/ops/no_external_requests_gate.sh
```

Manuell:
1. Internet am Testgerät deaktivieren.
2. App starten:

```bash
python kukanilea_app.py --host 127.0.0.1 --port 5051
```

3. Login + Dashboard + mindestens 3 Tools öffnen.

PASS wenn:
- Keine externen Asset-Requests im produktiven Renderpfad (Guardrail-Check grün).
- Keine unauthorized external URLs in Templates/Static assets.
- UI bleibt vollständig nutzbar.

Evidence:
- Guardrail Scan:
- External URL Scan:
- Offline-Start:
- UI-Sichtprüfung:
- Ergebnis: `PASS | FAIL`

---

## Gate 4 — Security Baseline & Contracts

```bash
./scripts/ops/security_gate.sh
./scripts/ops/contract_gate.sh
```

PASS wenn:
- Security baseline (CORS, Open Redirects, Error Handling, Rate Limiting) erfüllt ist.
- Alle 11 Tools die `/api/<tool>/summary` und `/api/<tool>/health` Contracts erfüllen.

Evidence:
- Security Gate:
- Contract Gate:
- Ergebnis: `PASS | FAIL`

---

## Gate 5 — Lizenzsteuerung (inkl. Sperrfall)

Pflichttests:
1. `AKTIV` => Normalbetrieb.
2. `GESPERRT` => Lock/Read-only greift.
3. SMB/NAS temporär down => definierter Grace-Flow + Audit.
4. Reaktivierung => Recovery ohne Datenverlust.

Empfohlene Nachweise:
- API/Log-Ausgaben der Lizenzprüfung.
- Audit-Events mit Timestamp.

PASS wenn:
- Alle vier Zustände reproduzierbar und dokumentiert sind.

Evidence:
- Test 1:
- Test 2:
- Test 3:
- Test 4:
- Ergebnis: `PASS | FAIL`

---

## Gate 6 — Backup & Restore Drill

Pflichttests:
1. Backup erstellen (verschlüsselt, mandantengetrennt).
2. Restore auf Testpfad/Testsystem.
3. Datenvergleich (Stichprobe: Projekte, Aufgaben, Dokumente, Zeiten).
4. RTO/RPO messen.

PASS wenn:
- Restore konsistent und innerhalb Ziel-RTO/RPO.

Evidence:
- Backup-Job:
- Restore-Job:
- Datenvergleich:
- RTO:
- RPO:
- Ergebnis: `PASS | FAIL`

---

## Gate 7 — KI lokal + Guardrails + Confirm-Gates

Pflichttests:
1. Lokales Modell ist aktiv (inkl. Fallback-Path).
2. Summary/Read-APIs funktionieren.
3. Jede schreibende Aktion erfordert Confirm-Gate.
4. Audit-Logs werden geschrieben.

Beispiel-Checks:

```bash
# health / summary endpoints projektabhängig prüfen
curl -s http://127.0.0.1:5051/api/system/status
curl -s http://127.0.0.1:5051/api/outbound/status
```

PASS wenn:
- Kein Write ohne explizite Bestätigung möglich ist.
- Injection-ähnliche Eingaben keine unkontrollierte Aktion auslösen.

Evidence:
- Modellstatus:
- Summary-Checks:
- Confirm-Gate-Checks:
- Audit-Log-Checks:
- Ergebnis: `PASS | FAIL`

---

## Finales Urteil

- Gate 1: `PASS | FAIL`
- Gate 2: `PASS | FAIL`
- Gate 3: `PASS | FAIL`
- Gate 4: `PASS | FAIL`
- Gate 5: `PASS | FAIL`
- Gate 6: `PASS | FAIL`
- Gate 7: `PASS | FAIL`

Freigabe:
- `GO` nur bei 7/7 PASS.
- Sonst: `NO-GO` + P0/P1-Owner + ETA.

---

## Optional: Kunden-Installationsprotokoll

- Kunde/Mandant:
- Gerät:
- Installationszeit Start/Ende:
- Offene Punkte:
- Nächster Termin:


## OPS-Release Nachschärfung (Production-Grade)

### Verifizierbare Backup-Artefakte (Pflicht)
- Backup-Run schreibt **immer**:
  - `checksum_sha256`
  - `backup_size_bytes`
  - `tenant_id`
  - `*.metadata.json` (Tenant, Dateiname, Größe, Checksum)
  - `*.snapshot.json` (Baseline für Restore-Compare)
- Bei SMB/NAS-Ausfall (`smbclient` fehlt/down) muss `mode=degraded_local` gesetzt sein und Artefakte lokal unter `instance/degraded_backups/<tenant>/` liegen.

### Restore-Datenintegrität (Pflicht)
- Restore muss Integrität vor Entpacken prüfen:
  - Checksum-Verify (`.sha256`)
  - Metadata-Verify (tenant/dateiname/size)
- Restore muss **Before/After-Compare** durchführen:
  - Baseline aus Backup-Snapshot (`*.snapshot.json`)
  - `restore_validation.py --phase after` gegen diese Baseline

### Lizenzzustände + Audit-Evidence (Pflicht)
- Zustände müssen nachweisbar durch Tests/Artefakte abgedeckt sein:
  - `AKTIV`
  - `GESPERRT`
  - `GRACE` (inkl. SMB down / unreachable)
- Nachweis: `tests/license/test_license_state_machine.py` + Gate-Evidence-Output.

### Deterministische Launch-Entscheidung
- Gate-Matrix bleibt `PASS/WARN/FAIL` pro Gate.
- Gesamtentscheidung ist deterministisch:
  - `GO` wenn `FAIL=0`
  - `NO-GO` wenn `FAIL>0`

### Degraded-Mode (SMB down) dokumentiert
- Betriebsanweisung:
  1. Backup läuft lokal weiter (`mode=degraded_local`).
  2. Restore nutzt lokale Fallback-Artefakte.
  3. Incident im Operations-Report vermerken.
  4. Nach NAS-Recovery Replikation/Abgleich starten.


## Ops Evidence Drill (License + Backup/Restore)

- Lizenzstatus muss in Evidence als `OK`, `WARN` oder `LOCKED` auftauchen.
- `LOCKED` ist **fail-closed** und führt deterministisch zu `NO-GO`.
- Backup-Evidence pro Tenant: `tenant_id`, `target_path`, `checksum_sha256`, `backup_size_bytes`, `compression_ratio`.
- Restore-Evidence: `verify_db=ok` und `verify_files=ok` plus `restore_validation=ok` und gemessene `rto_seconds`.
- Keine Secrets in Reports/Logs dokumentieren.

Siehe Beispiel: `docs/status/EVIDENCE_SAMPLE.md`.
