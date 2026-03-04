# KUKANILEA Launch Evidence Checklist

> Ziel: "Launch-Ready" wird **messbar**. Jeder Gate-Punkt braucht einen klaren Nachweis (Command + Output + PASS/FAIL).

## Verwendung

- Diese Checkliste wird pro Release-Kandidat (`rc-*`) und vor jeder Kundeninstallation ausgefüllt.
- Standardreport liegt unter: `docs/reviews/codex/LAUNCH_EVIDENCE_RUN_<YYYYMMDD>_<HHMMSS>.md`.
- Ein Gate ist nur **PASS**, wenn Command-Ausgabe und Akzeptanzkriterium erfüllt sind.

---

## Schnellstart (One-Command Gate)

```bash
scripts/ops/launch_evidence_gate.sh
```

- Das Skript erstellt einen timestamped Report mit PASS/WARN/FAIL und GO/NO-GO.
- Für Kundenfreigaben müssen alle WARN-Punkte aufgelöst oder explizit akzeptiert werden.

---

## Gate 1 — Repo- und CI-Evidence (Single Source of Truth)

### Zweck
Verhindert widersprüchliche Aussagen zu PR- und CI-Status.

### Commands
```bash
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
gh pr list --limit 20
gh run list --limit 20
```

### Akzeptanzkriterien
- Branch ist `main` oder definierter RC-Branch.
- Commit-Hash dokumentiert.
- Keine unklaren offenen PRs für den RC-Umfang.
- Relevante CI-Runs sind `completed` und `success`.

---

## Gate 2 — Core-Stabilität & lokaler Healthcheck

### Zweck
Stellt sicher, dass Core-Basis und operative Prüfungen stabil sind.

### Commands
```bash
./scripts/ops/healthcheck.sh
```

### Akzeptanzkriterien
- Healthcheck beendet sich mit Exit Code `0`.
- Route-, DB- und Guardrail-Checks laufen grün.

---

## Gate 3 — Offline/Zero-CDN Nachweis

### Zweck
Produkt muss ohne Internet stabil starten und vollständig rendern.

### Commands
```bash
rg -n "https?://" app/templates app/static || true
python kukanilea_app.py --host 127.0.0.1 --port 5051
```

### Manuelle Prüfung
- Netzwerk am Testgerät deaktivieren.
- Login + Dashboard + mindestens 3 Tools öffnen.
- Keine kaputten Styles, keine externen Ladefehler, keine Hänger.

### Akzeptanzkriterien
- Keine externen Requests in produktiven Assets/Templates.
- App startet offline reproduzierbar.
- Sichtprüfung ohne UI-Bruch.

---

## Gate 4 — White-Mode-Only Nachweis

### Zweck
Sovereign-11 UI bleibt strikt im White-Mode.

### Commands
```bash
rg -n "prefers-color-scheme\s*:\s*dark|data-theme=\"dark\"|theme-dark|--color-dark|\.dark\b" app/static/css app/templates
```

### Akzeptanzkriterien
- Keine Dark-Mode-Selektoren in produktiven CSS/Template-Dateien.

---

## Gate 5 — Lizenzsteuerung (SMB/Excel) inkl. Sperrfall

### Zweck
Validiert Geschäftsmodell: Aktiv, Sperre, Wiederfreigabe sind robust.

### Testfälle
1. Lizenzstatus `AKTIV` → Normalbetrieb.
2. Lizenzstatus `GESPERRT` → Lock-Screen / Read-only erzwingen.
3. SMB temporär nicht erreichbar → definierter Grace-Mode + Warnung + Audit.
4. Rückkehr zu `AKTIV` → Recovery ohne Datenverlust.

### Akzeptanzkriterien
- Zustandswechsel sind reproduzierbar und auditierbar.
- Kein unkontrollierter Vollzugriff bei `GESPERRT`.
- Recovery-Pfad dokumentiert und getestet.

---

## Gate 6 — Backup & Restore Drill (mandantenfähig)

### Zweck
Datensicherheit praktisch beweisen (nicht nur Backup-Skript vorhanden).

### Commands
```bash
./scripts/ops/backup_to_nas.sh
./scripts/ops/restore_from_nas.sh
```

### Pflichtprüfung
- Backup erzeugt, verschlüsselt und auf NAS abgelegt.
- Restore auf Testpfad/Testsystem erfolgreich.
- Stichproben-Datenvergleich (Dokumente, Aufgaben, Projekte, Zeiten) korrekt.
- RTO/RPO messen und dokumentieren.

### Akzeptanzkriterien
- Restore vollständig + konsistent.
- RTO/RPO innerhalb definierter Grenzwerte.

---

## Gate 7 — KI-Local-Run + Guardrails + Confirm-Gates

### Zweck
Sichert KI-Nutzen ohne Compliance-Risiko.

### Pflichtprüfung
- Lokales Modell geladen (inkl. Fallback).
- Tool-Summary-Abfragen funktionieren read-only.
- Potenziell gefährliche Aktionen verlangen Confirm-Gate.
- Audit-Events werden geschrieben.

### Akzeptanzkriterien
- Kein write-path ohne explizite Bestätigung.
- Injection-/Prompt-Missbrauch führt nicht zu unkontrollierter Aktion.

---

## Finales Launch-Urteil

- `GO` nur bei **0 FAIL** und dokumentierter Behandlung aller WARNs.
- Bei `FAIL`: Blocker als P0/P1 erfassen, Owner zuweisen, ETA setzen.

## Optional: Kundenbesuch Kurzprotokoll

- Kunde / Mandant:
- Gerät (z. B. ZimaBlade / Mini-PC):
- Installationszeit (Start/Ende):
- Offene Punkte:
- Nächster Termin:
