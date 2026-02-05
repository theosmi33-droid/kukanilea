# Project Status

## GOALS
- App-Factory + Blueprints für stabile, testbare Struktur.
- Auth & Tenant-Membership (keine Tenant-Eingabe im UI).
- Agent-Orchestrator mit deterministischen Tools und RBAC.
- Upload → Review → Archive mit Vorschlagslogik.

## TODO
- Upload-Job State Machine in DB persistieren.
- OCR-Fallback (Feature-Flag) hinzufügen.
- Messenger/Time-Tracking Feature-Flags als Stubs ergänzen.

## DONE
- `app/` Struktur mit `create_app()` + Blueprints.
- Seed-Skript für admin/dev User.
- Tenant-Header + Tenant-freies UI.
- Orchestrator + PolicyEngine + ToolRegistry erweitert.
- Google OAuth Platzhalter + Mail-Stub UI ergänzt (ohne Drittanbieter-Links).
- Smoke-Test + GitHub Actions Workflow + pytest.
- README/ROADMAP/PACKAGING aktualisiert.
- Wetter-Plugin Fallback angebunden.
