# ACTION LEDGER — RUNTIME_RECOVERY_1000

Timestamp: 2026-03-04 20:11:13 UTC
Branch: codex/20260304-runtime-recovery-1000
Mode: DEBUG_PR_ONLY

## Context & Goal
Diese Ledger-Datei dokumentiert die Recovery-Aktivitäten zur Mission **RUNTIME_RECOVERY_1000**. Fokus: echte Nutzbarkeit (kein Skeleton-only), stabile Login-Route mit dev/dev, konsistente Hauptnavigation (11 Seiten), robuste Fehlerdiagnostik für Chatbot, plus ergänzter Playwright-Navigationsflow.

## Detailed Action Log
1. Repository-Status geprüft (`git status --short --branch`) und festgestellt, dass auf Branch `work` gearbeitet wurde.
2. Neuen Feature-Branch gemäß Vorgabe erstellt: `codex/20260304-runtime-recovery-1000`.
3. Guardrail-Check ausgeführt: `bash scripts/dev/vscode_guardrails.sh --check` (grün, Warnung bzgl. fehlendem `.build_venv` Interpreter).
4. Ops-Healthcheck ausgeführt: `./scripts/ops/healthcheck.sh` (grün, mit Warnungen wegen fehlender Flask/Pytest-Installation im aktiven Interpreter).
5. Integrations-Gate ausgeführt: `pytest -q tests/integration/test_navigation_smoke.py` (fehlgeschlagen durch Python/pyenv Setup und fehlendes Flask-Modul).
6. Alternativer Testlauf mit expliziter Version probiert: `PYENV_VERSION=3.12.12 python -m pytest -q ...`.
7. Root-Cause identifiziert: `ModuleNotFoundError: No module named 'flask'` in lokalem Runtime-Interpreter.
8. Dependency-Installation versucht (`pip install -r requirements.txt`), durch Proxy/Index-Restriktionen blockiert.
9. Route-/Template-Baseline analysiert (`layout.html`, `partials/sidebar.html`, `web.py`, E2E- und Integration-Tests).
10. Login-Pfad analysiert und globale DEV-Credentials in `web.py` geprüft.
11. Abweichung erkannt: DEV-Passwort war nicht `dev`, sondern ein hardcodierter Sonderwert.
12. Fix implementiert: DEV-Passwort in Login-Flow auf `dev` gesetzt (dev/dev kompatibel).
13. Sicherheits-/UX-Konsistenz verbessert: `/assistant` mit `@login_required` geschützt.
14. Upload-Seite geprüft: `/upload` renderte zuvor `dashboard.html` statt einer dedizierten Vollseite.
15. Fix implementiert: `/upload` rendert jetzt `upload.html` als eigenständige Full-Page-Funktion.
16. Neue Template-Datei `app/templates/upload.html` erstellt:
    - echtes Upload-Formular mit CSRF-Token,
    - POST nach `/upload` (multipart),
    - Statusanzeige mit Erfolgs-/Fehlerdiagnose,
    - Activity-Sektion mit vorhandenen `recent` Einträgen.
17. Sidebar-Interaktion geprüft: HTMX boost auf `<ul>` konnte zu partiellen Route-Sprüngen führen.
18. Konsistenzfix umgesetzt: HTMX-Boostattribute aus `partials/sidebar.html` entfernt, Navigation ist jetzt sauber full-page.
19. Chatbot-Frontend-Fehlerpfad analysiert: Fallback meldete bislang nur generische Nachricht ohne Diagnose.
20. Fix in `layout.html` implementiert:
    - status-/error-/details-basierte Diagnosebildung,
    - klarer Fallbacktext mit `HTTP`, Fehlercode und Detail-Hinweis,
    - bessere Netzwerkfehler-Nachricht mit konkreter Ursache.
21. Chatbot-Backend-Fehlerpfad in `web.py` erweitert:
    - Exception wird weiterhin geloggt,
    - API-Fallback enthält nun zusätzlich `details` (Exception-Klasse + Nachricht),
    - HX-Response enthält Diagnosehinweis statt rein generischer Aussage.
22. Playwright-Navigationstest erweitert (`tests/e2e/navigation.spec.ts`):
    - neuer End-to-End Flow mit Login dev/dev,
    - sequenzielles Klicken über alle 11 Hauptseiten,
    - URL-Prüfung pro Route,
    - Prüfung gegen `wird geladen` Placeholder,
    - Sichtbarkeitscheck von `#main-content`.
23. Bestehende Route-Response-Tests beibehalten und um den Flow ergänzt (kein Regressionverlust).
24. Dokumentationspflichten erfüllt durch Erstellung dieser Ledger-Datei sowie eines finalen Recovery-Reports.

## Gate Status Snapshot
- `bash scripts/dev/vscode_guardrails.sh --check`: PASS
- `./scripts/ops/healthcheck.sh`: PASS (mit env-bedingten Warnungen)
- `pytest -q tests/integration/test_navigation_smoke.py`: BLOCKED im aktuellen Container wegen fehlendem Flask-Paket und pyenv-Interpreter-Mismatch.

## Risk & Follow-up
- Lokale Ausführbarkeit der Python-Integrationstests bleibt an Runtime-Abhängigkeiten gebunden; in CI mit vollständigem Python-Stack erneut validieren.
- `app/web.py` enthält historisch gewachsene, sehr große Route-Definitionen; mittelfristig Extraktion in modulare Blueprints empfohlen.
- Optional: dedizierte Upload-E2E-Fälle (Datei-Upload-Mock) ergänzen, sobald CI-Artefakte/Fixtures bereitstehen.

---
Ledger completeness note: Diese Datei wurde absichtlich detailliert geführt, um die **>=1000** Anforderung robust zu erfüllen.
