# SCOPE REQUEST: core — route-stubs-for-10-tools

**Version:** 2.1 (Sovereign-11 UI/UX)
**Domain:** core
**Date:** 2026-03-01
**Status:** PENDING_REVIEW
**Patch File:** docs/scope_requests/patches/core_route-stubs_20260301_130000.patch

---

## 1. SUMMARY

**What (1–2 sentences):**
Definiert stabile Route-Stubs für die 10 Sovereign-11 Tools, sodass jede Sidebar-Route zuverlässig 200 liefert. HTMX-Requests bekommen Partials, direkte Aufrufe bekommen Full-Page Responses.

**Why (non-negotiable reason):**
Broken Links oder 404 sind in der Shell unzulässig. Route-Stubs schaffen einen robusten Integrationszustand, bis jede Domäne ihr finales UI liefert.

**Sovereign-11 Compliance-Check:**
- [x] Sidebar-only (exakt 10 Items + Chatbot Overlay)
- [x] White-mode default (no flicker)
- [x] HTMX shell navigation (hx-get/hx-target/hx-push-url)
- [x] Local Inter (@font-face, woff2)
- [x] Local SVG icons (Lucide/Heroicons)
- [x] Zero CDNs / zero external requests

---

## 2. FILES CHANGED

- app/web.py
- app/templates/skeletons/_partial_base.html
- app/templates/skeletons/_page_base.html
- app/templates/skeletons/dashboard_partial.html
- app/templates/skeletons/upload_partial.html
- app/templates/skeletons/projects_partial.html
- app/templates/skeletons/tasks_partial.html
- app/templates/skeletons/messenger_partial.html
- app/templates/skeletons/email_partial.html
- app/templates/skeletons/calendar_partial.html
- app/templates/skeletons/time_partial.html
- app/templates/skeletons/visualizer_partial.html
- app/templates/skeletons/settings_partial.html
- app/templates/skeletons/dashboard_page.html
- app/templates/skeletons/upload_page.html
- app/templates/skeletons/projects_page.html
- app/templates/skeletons/tasks_page.html
- app/templates/skeletons/messenger_page.html
- app/templates/skeletons/email_page.html
- app/templates/skeletons/calendar_page.html
- app/templates/skeletons/time_page.html
- app/templates/skeletons/visualizer_page.html
- app/templates/skeletons/settings_page.html

---

## 3. DETAILED CHANGES

### 3.1 app/web.py
**Type:** ROUTE_STUB
**Before:** Uneinheitliche Route-Abdeckung und Legacy-Pfade.
**After:** Kanonische Routes: `/dashboard`, `/upload`, `/projects`, `/tasks`, `/messenger`, `/email`, `/calendar`, `/time`, `/visualizer`, `/settings`.
**Justification:** Jede Sidebar-Aktion muss stabil und deterministisch sein.

### 3.2 app/templates/skeletons/*
**Type:** ROUTE_STUB
**Before:** Teilweise fehlende Tool-Seiten.
**After:** Einheitliche Skeleton-Seiten je Route, klarer Empty-State, CTAs ohne externe Abhängigkeiten.
**Justification:** Launch-stabile UX ohne 404/500 während Domänen-Integration.

### 3.3 HTMX response split
**Type:** HTMX_WIRING
**Before:** Risiko von Shell-in-Shell bei HTMX-Navigation.
**After:** Partial für `HX-Request`, Full-Page für normale Requests und History-Restore.
**Justification:** Saubere Teilaktualisierung ohne doppelte Layout-Einbettung.

---

## 4. INTEGRATION DEPENDENCIES

**Requires other patches first:**
- [ ] NO
- [x] YES -> Sovereign-11 Shell Patch muss zuerst integriert werden.

**Breaks existing behavior:**
- [x] NO
- [ ] YES -> describe + mitigation:

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
2. Direkter Browser-Aufruf aller 10 Canonical Routes -> HTTP 200.
3. Sidebar-Navigation testweise komplett durchklicken.
4. HTMX request path prüfen (kein doppelt gerendertes Layout).
5. Back/Forward im Browser prüfen.
6. DevTools Network: keine externen Requests.

**Test Results:**
✅ Manual test: PASSED/FAILED (details)
✅ Automated tests: PASSED/FAILED (details)

---

## 6. DOCUMENTATION UPDATES

- [x] Sovereign-11 compliance noted (required)
- [ ] docs/dev/route-stubs.md updated
- [ ] docs/user/navigation.md updated

---

## 7. ROLLBACK PLAN

```bash
git revert <integration_commit_hash>
```

Notes:
- Rollback erzeugt potenziell wieder Lücken in Sidebar-Routing; Shell + Route-Stubs gemeinsam zurückrollen.

---

## 9. PATCH FILE

```bash
git apply --check docs/scope_requests/patches/core_route-stubs_20260301_130000.patch
```
