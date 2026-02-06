# Bug Report: Chat Not Responding

## Symptoms
- Chat request hangs or shows generic network error.
- Browser console shows JSON parse errors after `/api/chat`.

## Root Cause
- API endpoints returned HTML redirect responses (login guard) and non‑JSON error bodies.
- Client attempted `res.json()` and failed, leaving the UI in error state.

## Fix
- Ensure `/api/*` endpoints return JSON error envelopes.
- Add client‑side retry with backoff and safe JSON parsing.
- Add CSRF token propagation and request‑id headers.
