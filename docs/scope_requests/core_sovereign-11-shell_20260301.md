# SCOPE REQUEST: core — sovereign-11-shell

**Version:** 2.1 (Sovereign-11 UI/UX)
**Domain:** core
**Date:** 2026-03-01
**Status:** PENDING_REVIEW
**Patch File:** docs/scope_requests/patches/core_sovereign-11-shell_20260301_120000.patch

---

## 1. SUMMARY

**What (1–2 sentences):**
Ersetzt die App-Shell durch das Sovereign-11 Layout: Sidebar-only (240px) mit exakt 10 Tools plus Chatbot-Overlay. HTMX-Navigation lädt Inhalte in `#main-content` ohne Shell-Reload.

**Why (non-negotiable reason):**
Ohne diese Shell bleibt die Navigation inkonsistent und fehleranfällig. Die Änderung erzwingt eine einzige, stabile Bedienstruktur ohne zusätzliche Menüs/Links.

**Sovereign-11 Compliance-Check:**
- [x] Sidebar-only (exakt 10 Items + Chatbot Overlay)
- [x] White-mode default (no flicker)
- [x] HTMX shell navigation (hx-get/hx-target/hx-push-url)
- [x] Local Inter (@font-face, woff2)
- [x] Local SVG icons (Lucide/Heroicons)
- [x] Zero CDNs / zero external requests

---

## 2. FILES CHANGED

- app/templates/layout.html
- app/templates/partials/sidebar.html
- app/static/css/design-system.css
- app/static/js/vendor/htmx.min.js
- app/static/js/shell_nav.js
- app/static/fonts/inter/inter.css
- app/static/fonts/inter/Inter-Regular.woff2
- app/static/fonts/inter/Inter-SemiBold.woff2
- app/static/icons/sovereign/layout-dashboard.svg
- app/static/icons/sovereign/upload-cloud.svg
- app/static/icons/sovereign/kanban.svg
- app/static/icons/sovereign/check-square.svg
- app/static/icons/sovereign/message-square.svg
- app/static/icons/sovereign/mail.svg
- app/static/icons/sovereign/calendar.svg
- app/static/icons/sovereign/clock.svg
- app/static/icons/sovereign/file-digit.svg
- app/static/icons/sovereign/settings.svg

---

## 3. DETAILED CHANGES

### 3.1 app/templates/layout.html
**Type:** SIDEBAR_SLOT | HTMX_WIRING | LOCAL_ASSET
**Before:** Mehrere Navigationselemente/Links außerhalb einer strikt definierten 10-Tool-Sidebar.
**After:** Feste Shell mit Sidebar (240px), HTMX-Linking (`hx-get`, `hx-target`, `hx-push-url`), keine zusätzliche Navigation.
**Justification:** Einheitliches Bedienmodell reduziert Integrationsfehler und verhindert Link-Drift.

### 3.2 app/static/css/design-system.css
**Type:** CSS_TOKENS
**Before:** Uneinheitliche Token/Abstände.
**After:** White-Mode Standard, 8pt-grid Tokens, klarer Active-State und Fokusstil.
**Justification:** Konsistenz und schnellere Umsetzung pro Domäne.

### 3.3 app/static/js/shell_nav.js
**Type:** OTHER
**Before:** Active-State nicht robust nach HTMX swaps.
**After:** Active-State nach Route und nach HTMX swap konsistent.
**Justification:** Verhindert Navigations-Fehlzustände bei teilweiser Inhaltsaktualisierung.

---

## 4. INTEGRATION DEPENDENCIES

**Requires other patches first:**
- [x] NO
- [ ] YES -> list:

**Breaks existing behavior:**
- [ ] NO
- [x] YES -> alte sekundäre Navigation wird entfernt; Mitigation: alle Zugriffe über Sidebar standardisiert.

**New dependencies:**
- [x] NO
- [ ] YES -> list:

**Config/.env changes:**
- [x] NO
- [ ] YES -> list keys (NO secrets):

---

## 5. TESTING

**Manual Test Steps:**
1. Start `python kukanilea_app.py`.
2. Sidebar zeigt exakt 10 Items, Chatbot bleibt Overlay.
3. Klick jedes Item -> Inhalt lädt im Main-Bereich, URL wird aktualisiert.
4. Browser Back/Forward prüfen.
5. DevTools Network: keine externen CDN Requests.
6. Reload auf mehreren Seiten: White-Mode ohne Flackern.

**Test Results:**
✅ Manual test: PASSED/FAILED (details)
✅ Automated tests: PASSED/FAILED (details)

---

## 6. DOCUMENTATION UPDATES

- [x] Sovereign-11 compliance noted (required)
- [ ] docs/user/layout.md updated
- [ ] docs/dev/sovereign-11-shell.md updated

---

## 7. ROLLBACK PLAN

```bash
git revert <integration_commit_hash>
```

Notes:
- Nach Rollback Sidebar, Route-Mapping und Asset-Pfade gegenprüfen.

---

## 9. PATCH FILE

```bash
git apply --check docs/scope_requests/patches/core_sovereign-11-shell_20260301_120000.patch
```
