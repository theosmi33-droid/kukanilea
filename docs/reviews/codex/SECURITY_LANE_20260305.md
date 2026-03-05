# Security Lane Review — 2026-03-05

## Scope
- Lane: `security`
- Ziel: Security-by-default ohne Regressionen

## Security Matrix

| Bereich | Erzwingung / Härtung | Nachweis |
|---|---|---|
| Confirm-Gates (write-like Admin-Settings-Routen) | Alle kritischen mutierenden Routen unter `/admin/settings/*` erzwingen `confirm` und werden auf Injection-Muster geprüft. Regressionen sind per Testmatrix für positive und negative Confirm-Fälle abgedeckt, inklusive Lizenz-Upload, Backup-Restore und Mesh-Key-Rotation. | `tests/security/test_confirm_and_injection_gates.py` |
| CSP | CSP wurde weiter eingeschränkt: `frame-src 'none'` (statt `'self'`) und `media-src 'self'` (ohne `data:`). Keine Lockerung durch `blob:`/Remote-Quellen. Inline-Ausnahmen bleiben explizit auf `script-src`/`style-src` dokumentiert. | `app/security/csp.py`, `tests/security/test_csp_policy.py` |
| Session Defaults | Session-Cookies bleiben standardmäßig `HttpOnly`; `SameSite` wird auf `Lax`/`Strict` normalisiert; `Secure` wird in Non-Dev erzwungen. Zusätzlich wird `SESSION_COOKIE_SECURE` robust aus bool/string normalisiert. Bei `Secure` wird konsistent `__Host-`-Cookie-Policy durchgesetzt. | `app/__init__.py`, `tests/security/test_session_security_defaults.py` |
| Gate-Helper | Confirm-/Injection-Helper bleiben deterministisch und testabgesichert (Token-Normalisierung, SQL/XSS/Prompt-Injection-Erkennung). | `app/security/gates.py`, `tests/security/test_security_gate_helpers.py` |

## Hinweise
- Preflight via `gh` war in dieser Umgebung nicht ausführbar (`gh` nicht installiert, API-Zugriff 403). Daher kein belastbarer PR-Overlap-Abgleich gegen Remote-PR-Dateilisten möglich.
