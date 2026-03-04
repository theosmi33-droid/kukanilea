# KUKANILEA Launch Evidence Checklist

Ziel: Launch-Readiness ist nur gültig, wenn sie reproduzierbar messbar ist. Kein Prozent-Status ohne Evidence.

## Nutzung

- Vor jedem RC-Release und vor jeder Kundeninstallation ausführen.
- Ergebnis unter `docs/reviews/codex/` oder `docs/status/` ablegen.
- `GO` nur bei 6/6 PASS.

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
scripts/ops/launch_evidence_gate.sh --fast
```

Hinweis (wichtig für CI):
- Bei Log-Pipelines immer mit `pipefail` ausführen, damit Gate-Fehler nicht als false-green enden:

```bash
set -o pipefail
scripts/ops/launch_evidence_gate.sh | tee /tmp/gate.txt
```
- Exit-Code-Konvention:
  - `0` = GO/GO with Notes
  - `3` = fehlende Abhängigkeit/Umgebung (z. B. `gh`, `rg`, `REPO`)
  - `4` = mindestens ein Gate ist FAIL


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
- Healthcheck Exit-Code 0.
- Pytest ohne Failures.

Evidence:
- Working tree:
- Healthcheck:
- Pytest:
- Ergebnis: `PASS | FAIL`

---

## Gate 3 — Offline/Zero-CDN

```bash
python scripts/ops/verify_guardrails.py
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
- UI bleibt vollständig nutzbar.

Evidence:
- Scan:
- Offline-Start:
- UI-Sichtprüfung:
- Ergebnis: `PASS | FAIL`

---

## Gate 4 — Lizenzsteuerung (inkl. Sperrfall)

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

## Gate 5 — Backup & Restore Drill

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

## Gate 6 — KI lokal + Guardrails + Confirm-Gates

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

Freigabe:
- `GO` nur bei 6/6 PASS.
- Sonst: `NO-GO` + P0/P1-Owner + ETA.

---

## Optional: Kunden-Installationsprotokoll

- Kunde/Mandant:
- Gerät:
- Installationszeit Start/Ende:
- Offene Punkte:
- Nächster Termin:
