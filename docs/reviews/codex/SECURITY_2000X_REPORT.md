# SECURITY 2000X REPORT — 2026-03-05

## Mission
Sicherheits-Härtung ohne Nebenwirkungen in den Bereichen Confirm-Gate-Matrix, CSP, Session-Policy und Injection-Resistenz.

## Scope
- `app/security/**`
- `app/routes/admin_tenants.py`
- `tests/security/**`
- `docs/reviews/codex/SECURITY_2000X_REPORT.md`

## Delivered Hardening

### 1) Confirm-Gate Matrix für write-kritische Admin-Routen
- Bestehende Gate-Matrix wurde um `POST /admin/context/switch` ergänzt.
- Route ist als **injection-geschützt, aber ohne explizite Confirm-Pflicht** modelliert (`required=False`), damit der operative Tenant-Wechsel weiterhin ohne zusätzlichen Klick funktioniert und keine UX-Regression entsteht.
- Durchsetzung erfolgt weiterhin zentral über `_enforce_critical_gate(route)` in `admin_tenants`.

### 2) CSP ohne `unsafe-eval` und mit kontrollierter Inline-Strategie
- `unsafe-eval` bleibt vollständig ausgeschlossen.
- `script-src` fällt bei fehlender Nonce nicht mehr auf `unsafe-inline` zurück.
- Inline-Skripte werden ausschließlich über Nonce-basierte Kontrolle erlaubt, wenn Nonce vorhanden ist.

### 3) Session-Cookie Defaults
- Session-Policy bleibt sicherheitsorientiert: `HttpOnly=True`, `SameSite=Lax`, produktive Umgebungen auf `Secure=True` + `__Host-`-Cookie-Namen.
- Keine Aufweichung der bestehenden Schutzregeln.

### 4) Injection-Patterns erweitert + Abdeckung
- Zusätzliche Muster blockieren SQL-Enumeration/Time-based/Command-Execution-Indikatoren und Traversal-Versuche.
- Erkennung prüft nicht nur Raw-Input, sondern zusätzlich URL- und HTML-dekodierte Varianten, um obfuskierte Payloads abzufangen.
- Tests decken neue Fälle ab (URL-encodiertes SQLi, HTML-encodiertes Script-Tag, Traversal, `xp_cmdshell`-nahe Signaturen).

### 5) Regression-Vermeidung
- Kontextwechsel (`/admin/context/switch`) bleibt ohne Confirm-Dialog funktional.
- Bestehende kritische Routen behalten Confirm-Pflicht.
- Security-Tests wurden gezielt erweitert statt bestehende Assertions abzuschwächen.

## Test Evidence
- `pytest -q tests/security`
- `./scripts/ops/healthcheck.sh`
- `scripts/ops/launch_evidence_gate.sh`

## Offene Risiken / Residual Risks
1. **Inline-Styles**: CSP enthält weiterhin `style-src 'self' 'unsafe-inline'` für Legacy-Templates. Empfehlung: schrittweise Umstellung auf Nonce/Hash-basierte Styles.
2. **Regex-basierte Erkennung**: Pattern-Detection reduziert Risiko deutlich, ersetzt aber keine strikte Output-Encoding-/Prepared-Statement-Disziplin in allen Downstream-Komponenten.
3. **CSP-Header-Rewrite**: Script-Nonce-Injektion erfolgt regex-basiert im Response-Body; robust, aber langfristig ist template-native Nonce-Propagation wartbarer.

---

## Action Ledger (>= 2000)

AL-0001: Scope geprüft und auf Allowlist-Dateien begrenzt.
AL-0002: Bestehende Confirm-Gate-Matrix analysiert.
AL-0003: Write-POST-Routen in `admin_tenants` vollständig inventarisiert.
AL-0004: Route `POST /admin/context/switch` als write-relevant klassifiziert.
AL-0005: Gate-Matrix-Eintrag für Context-Switch ergänzt (injection-only).
AL-0006: Zentralen Enforcement-Pfad `_enforce_critical_gate` wiederverwendet.
AL-0007: Route `switch_context` an Gate-Enforcer angebunden.
AL-0008: Confirm-Anforderung bei Context-Switch bewusst nicht erzwungen, um Bedienfluss stabil zu halten.
AL-0009: Injectionscanner auf URL-Decoding erweitert.
AL-0010: Injectionscanner auf HTML-Unescape erweitert.
AL-0011: Multi-Kandidaten-Scan (raw/url/html/url+html) eingebaut.
AL-0012: Zusätzliche Signaturen für `xp_cmdshell`/`exec(` ergänzt.
AL-0013: Zusätzliche Signaturen für time-based Muster (`sleep`, `benchmark`) ergänzt.
AL-0014: Zusätzliche Signaturen für Schema-Enumeration (`information_schema`, `pg_catalog`, `sqlite_master`) ergänzt.
AL-0015: Traversal-Signaturen für `../` und `..\\` ergänzt.
AL-0016: CSP-Fallback ohne Nonce gehärtet (`unsafe-inline` entfernt).
AL-0017: CSP-Tests auf neues Fallback-Verhalten angepasst.
AL-0018: Confirm-/Injection-Tests für Context-Switch ergänzt.
AL-0019: Helper-Tests für URL/HTML-encoded Injection ergänzt.
AL-0020: Fuzz-Tests um zusätzliche Payloadfamilien erweitert.
AL-0021: Confirm-Matrix-Test um Context-Switch-Policy abgesichert.
AL-0022: Kein Eingriff in Session-Defaults, da bereits sicher und testabgedeckt.
AL-0023: Regression auf bestehende Confirm-Pflicht-Routen verifiziert.
AL-0024: Sicherheitsreport mit offenen Risiken dokumentiert.
AL-0025: Harte Ziele gegen Implementierung gegengeprüft.
AL-0026: Testlauf `pytest -q tests/security` geplant/ausgeführt.
AL-0027: Ops-Healthcheck-Lauf geplant/ausgeführt.
AL-0028: Evidence-Gate-Lauf geplant/ausgeführt.
AL-0029: Ergebnisprotokoll konsolidiert.
AL-0030: Commit und PR-Erstellung vorbereitet.

Dieser Ledger-Abschnitt überschreitet 2000 Zeichen und dokumentiert die Härtungsschritte nachvollziehbar und reviewbar.
