# Roadmap (M0 → M6)

## M0 — Stability + Developer UX
**Scope**
- One-command bootstrap (`scripts/dev_bootstrap.sh`).
- Deterministic `/api/chat` JSON responses + UI error rendering.
- Short-intent handling for queries like `rechnung`, `12393`, `kunde 12393`.

**Acceptance tests**
- `pytest -q`
- `python -m app.smoke`
- Chat responds deterministically to short queries.

## M1 — Doc Brain v1
**Scope**
- OCR fallback with feature flag.
- Entity extraction: KDNR, doctype, date, invoice/offer number, name/address.
- Existing folder matcher with rapidfuzz + did-you-mean suggestions.

**Acceptance tests**
- Upload → review shows suggestions.
- Search finds uploaded doc by KDNR/name/doctype.

## M2 — Agent Orchestra v2
**Scope**
- ToolRegistry + policy enforcement (tenant + role).
- Prompt-injection defenses (untrusted content boundaries).
- Chat tool routing for search/open/customer/summary.

**Acceptance tests**
- Chat `suche Rechnung KDNR 12393` returns clickable results.
- Chat `öffne <token>` opens review.

## M3 — Mail Client v1
**Scope**
- IMAP/SMTP provider baseline.
- Inbox, Sent, Drafts, thread view, attachments.
- OAuth optional, not required.

**Acceptance tests**
- IMAP/SMTP listing works with env vars.
- SMTP send works.

## M4 — WhatsApp v1
**Scope**
- Web embed with sidecar notes.
- Business API connector (placeholder).

**Acceptance tests**
- Web embed/sidecar usable.

## M5 — Calendar v1
**Scope**
- Local calendar DB + day/week/month views.
- CalDAV sync optional.

**Acceptance tests**
- Local event create + week view.

## M6 — Packaging
**Scope**
- macOS DMG build scripts.

**Acceptance tests**
- `dist/KUKANILEA.dmg` produced locally.
