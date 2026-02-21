# KUKANILEA Release Gates (Beta / RC / Prod)

## Zweck
Release Gates sind verbindliche **Pass/Fail-Kriterien** für Qualität, Sicherheit und Distribution. Sie machen Freigaben für Beta, RC und Produktion deterministisch und auditierbar.

## Prioritäten
- `P0` (Blocker): Security-Leak, Datenverlust, Login/Session-Ausfall, Installer-/Update-Blocker.
- `P1` (hoch): starke UX-Blockaden, wiederkehrende Fehler, relevante Performance-/Stabilitätsprobleme.
- `P2` (nice): Polishing und kleinere Inkonsistenzen.

## Abnahme-Matrix

| Gate | Beta | RC | Prod | Evidence | How to verify | Owner |
|---|---|---|---|---|---|---|
| Security (Tenant/RBAC/CSP/Session) | Keine bekannten P0-Leaks | 0 offene P0, 0 offene High | Externer Security-Check + 0 High | CI-Berichte, Security Findings, Request-IDs, Audit-Logs | Security- und Regression-Gates ausführen, offene Findings gegen Severity-Policy prüfen | Eng + Security Lead |
| UX Kernflows (Top-20) | ≥80% Pass | ≥95% Pass | 100% Pass für kritische Flows | UX-Flow-Protokoll, Screenshots, Issue-Links | Top-20-Flow-Liste gegen aktuelle Build-Version durchtesten | QA/UX |
| Error-UX (keine Sackgassen) | Fehlerseiten mit Reload/Zurück/Dashboard | + Request-ID überall konsistent | + Support-Runbook verifiziert | Fehler-Screenshots, Logs mit Request-ID, Support-Runbook | 403/404/500/Offline/Provider-down manuell prüfen, Korrelation Request-ID ↔ Log validieren | Eng + QA |
| Distribution macOS/Windows | Installer bauen & starten | Signierung aktiv | Signierung + Notarization/SmartScreen stabil | Build-Artefakte, Signatur-Infos, Release-Assets | Frisch installieren, starten, Basisflows prüfen; Signatur-/Notarization-Status verifizieren | Release Captain |
| Update/Rollback | Update manuell testbar | Rollback nachweisbar | Signiertes Manifest + Rollback dokumentiert | Update-Logs, Hash/Manifest, Rollback-Protokoll | Update-Flow in Testinstanz ausführen, Fehlerfall simulieren, Rollback validieren | Eng + Release Captain |
| Compliance/Privacy | Asset-/Request-Inventar vorhanden | Lizenz-/Drittanbieterliste vollständig | Freigabe-Checklist komplett abgeschlossen | Inventarlisten, Lizenz-Notices, Freigabeprotokoll | Externe Requests prüfen, Third-Party-Liste mit Build-Inhalt abgleichen, Checklist sign-off | Compliance Owner |
| Performance/Stabilität | 15–20 min Smoke ohne Blocker | 60 min Dauerlast ohne P1 | Reproduzierbarer Lasttest + Grenzwerte definiert | Testprotokolle, Laufzeitmetriken, Crash-/Error-Logs | Definierte Lastprofile laufen lassen und gegen Schwellwerte auswerten | Eng + QA |
| KI-Verfügbarkeit (lokal/fallback) | Primary+Fallback funktionieren | Ausfall-Fallback ohne UI-Blockade | Offline-First + Recovery-Runbook | Status-Snapshots, Fallback-Logs, Recovery-Doku | Primary/Fallback absichtlich ausfallen lassen, UI-Reaktion und Recovery prüfen | Eng (AI) |

## Pass/Fail Definition pro Gate

### Security (Tenant/RBAC/CSP/Session)
- Pass: Keine offenen P0/High Findings, serverseitige Enforcement nachweisbar.
- Fail: Jeder offene P0/High oder nachweisbarer Tenant/AuthZ-Bypass.

### UX Kernflows
- Pass: Zielquote je Stufe erreicht, kritische Flows ohne Sackgasse.
- Fail: Quote unterschritten oder kritischer Flow blockiert.

### Error-UX
- Pass: Fehler bleiben in App-Shell, klare Recovery-Aktionen, Request-ID sichtbar.
- Fail: Raw-JSON/Dead-End/fehlende Recovery-Option.

### Distribution
- Pass: Installer startet stabil, Signaturanforderung je Stufe erfüllt.
- Fail: Install/Start blockiert oder Signierungspflicht nicht erfüllt.

### Update/Rollback
- Pass: Update reproduzierbar, Rollback funktioniert deterministisch.
- Fail: Kein verlässlicher Rollback oder unvalidierter Update-Pfad.

### Compliance/Privacy
- Pass: Inventare vollständig, Freigaben dokumentiert, offene Risiken akzeptiert/nachverfolgt.
- Fail: Fehlende Nachweise bei High-Risk-Bereichen.

### Performance/Stabilität
- Pass: Lastprofile ohne Blocker/P1-Verstöße in Zielstufe.
- Fail: Abstürze, Freeze oder Überschreitung definierter Grenzwerte.

### KI-Verfügbarkeit
- Pass: Lokaler Primary/Fallback stabil, UI bleibt bedienbar bei Ausfällen.
- Fail: Provider-Ausfall blockiert Nutzerfluss oder Recovery fehlt.

## Go/No-Go Regeln
1. **No-Go**, wenn ein `P0` offen ist.
2. **No-Go**, wenn Kernflow Login/CRM/Tasks/Docs/AI in einem Ziel-OS blockiert.
3. **No-Go**, wenn Update ohne verlässlichen Rollback deployed wird.
4. **Go**, wenn alle RC-Kriterien erfüllt und zwei aufeinanderfolgende grüne CI-Läufe vorliegen.

## Exception Process
- Genehmiger: Release Captain + Security Lead + Produktverantwortung.
- Dokumentation: Issue/Decision-Record mit Risiko, Scope, betroffenen Gates.
- Pflichtfelder: Kompensationsmaßnahme, Verantwortliche, **Sunset-Datum**.
- Nachverfolgung: Exception bleibt bis Sunset-Datum im Release-Board als `Open Risk`.

## References
- OWASP Broken Access Control: <https://owasp.org/Top10/2025/A01_2025-Broken_Access_Control/>
- NIST AC-6 Least Privilege: <https://nist-sp-800-53-r5.bsafes.com/docs/3-1-access-control/ac-6-least-privilege/>
- Apple Platform Security (Code Signing): <https://support.apple.com/en-by/guide/security/sec3ad8e6e53/web>
- Apple Developer ID: <https://developer.apple.com/developer-id/>
- Microsoft Desktop App Certification / Authenticode: <https://learn.microsoft.com/en-us/windows/win32/win_cert/certification-requirements-for-windows-desktop-apps-v3-3>
- Microsoft SmartScreen FAQ: <https://feedback.smartscreen.microsoft.com/smartscreenfaq.aspx>
