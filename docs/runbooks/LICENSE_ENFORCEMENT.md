# License Enforcement — Operational Notes

Stand: 2026-02-19

## Scope
- Laufzeit-Enforcement fuer Trial/Lizenz inkl. Read-only und Grace.
- Aktivierung ueber `/license`.
- Operative Debug-Hinweise fuer Offline-/Remote-Validierung.

## File Map
- `app/license.py`: Signaturpruefung, Online-Validierung, Grace-Logik, Laufzeitstatus.
- `app/__init__.py`: Laden des Lizenzstatus beim App-Start, globaler Read-only-Guard.
- `app/web.py`: Lizenz-UI (`/license`) inkl. Aktivierungspfad.
- `app/config.py`: Lizenz-/Grace-/Validation-Umgebungsvariablen.
- `docs/LICENSING.md`: Funktionale und Security/Privacy-Doku.
- `tests/test_license_online_validation.py`: Kernlogik fuer Online/Grace.
- `tests/test_license_ui.py`: UI-/Aktivierungsfluss inkl. Read-only-Aktivierung.
- `tests/stubs/license_server_stub.py`: Lokaler Validation-Stub fuer Tests.
- `tests/test_license_offline_and_grace.py`: Stub-gestuetzte Offline/Grace-Tests.

## Failure Modes (deterministisch)
- `trial_expired`: Trial ist abgelaufen -> `READ_ONLY=true`.
- `license_expired`: Signierte Lizenz ist lokal abgelaufen -> `READ_ONLY=true`.
- `device_mismatch`: Lizenz ist an anderes Device gebunden -> `READ_ONLY=true`.
- `license_grace_offline`: Validation nicht erreichbar, aber Grace-Fenster aktiv -> nutzbar.
- `license_invalid_remote` / provider reason (z. B. `revoked`): Remote invalid -> `READ_ONLY=true`.

## Troubleshooting
| Symptom | Check | Aktion |
|---|---|---|
| Instanz bleibt read-only | `/license` Status + `LICENSE_REASON` prüfen | Gueltige Lizenz neu aktivieren, dann Seite neu laden |
| Grace unerwartet abgelaufen | `KUKANILEA_LICENSE_CACHE_PATH` und `grace_expires` pruefen | Zeit/Clock-Drift korrigieren, Lizenz erneut validieren |
| Validation-Server nicht erreichbar | `KUKANILEA_LICENSE_VALIDATE_URL`/`LICENSE_SERVER_URL` pruefen | Endpoint/Netzwerk reparieren, Grace beobachten |
| CI flaky bei Lizenztests | Sicherstellen, dass lokale Stub-URL genutzt wird | `tests/stubs/license_server_stub.py` verwenden |

## Security & Privacy
- Lizenzaktivierung ist absichtlich auch im Read-only-Modus erlaubt, damit gesperrte Instanzen ohne CLI reaktiviert werden koennen.
- Keine Secrets im UI/Logs anzeigen (keine Klartext-Lizenzschluessel in Meldungen).
- Hardware-Fingerprint ist ein gehashter Online-Identifier (pseudonymisiert, nicht anonym); nur minimal speichern und nicht in Logs ausgeben.
