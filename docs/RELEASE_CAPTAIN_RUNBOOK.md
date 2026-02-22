# Release Captain Runbook (Kukanilea)

Dieses Dokument definiert die Schritte zur Vorbereitung und Verifizierung eines Releases.

## 1. Vorbedingungen (Prerequisites)
- [ ] Alle PRs der Phasen `codex/pr-docs-only` und `codex/pr-hardening-bench` sind gemerged.
- [ ] Endurance Runner (60 min) ist ohne P1-Fehler durchgelaufen.
- [ ] Distribution-Gate ist auf macOS/Windows BLOCKED (falls Creds fehlen) – dies ist KEIN No-Go Grund für den RC.

## 2. Evidence Pack generieren (Automatisierung)

Führen Sie folgendes Kommando im Projekt-Root aus:

```bash
python3 scripts/generate_evidence_pack.py
```

Dieses Skript erzeugt ein JSON-Summary unter `dist/evidence/`.

## 3. Go/No-Go Checkliste

| Bereich | Kriterium | Status | Link |
|---------|-----------|--------|------|
| **Security** | 0 High CVEs (SBOM) | [ ] | `dist/evidence/sbom.cdx.json` |
| **UX/a11y** | EN 301 549 Baseline PASS | [ ] | `reports/REPORT_HARDENING_UX.md` |
| **Stability** | Endurance (60 min) | [ ] | `triage_report.json` |
| **Compliance** | CRA Reporting Ready | [ ] | `docs/SECURITY_REPORTING_CRA.md` |

## 4. Release-Entscheidung

- **GO:** Alle Kriterien der Checkliste sind erfüllt.
- **NO-GO:** Mindestens ein P1-Fehler oder fehlende Evidence (außer BLOCKED Distribution).

---
*Letzte Aktualisierung: 22.02.2026*
