# Stable UI E2E Test Contracts

This document defines **selector and timing contracts** used by Playwright tests to reduce flakiness.

## Shell readiness contract
- `#main-content` must exist after successful page navigation.
- `#main-content[data-page-ready="1"]` indicates the page is fully interactive.
- No final page state should include transient loading copies like:
  - `wird geladen`
  - `Lade Quellen`

## Navigation contract
- Side navigation links must expose deterministic href routes, e.g. `a[href="/dashboard"]`.
- Active nav link should expose:
  - `.nav-link[data-route="<route>"]`
  - `aria-current="page"`
  - `data-nav-active="1"`

## Authentication contract for E2E
- Login form fields keep their user-facing accessibility names:
  - username textbox (`/username/i`)
  - password textbox (`/password/i`)
- Submit button keeps an accessible name matching one of:
  - `anmelden`
  - `login`
  - `system betreten`
  - `submit`

## Responsive contract
- Mobile viewport must not produce horizontal overflow.
- Desktop keeps sidebar visible.
- Mobile navigation (`.mobile-bottom-nav`) is optional and asserted only when present.

## Persistent UI state contract
- Sidebar collapse toggle writes `localStorage['ks_sidebar_collapsed'] = '1'`.
- Reloaded page reflects collapsed shell class on `<html>` (`sidebar-collapsed`).

## Visualizer resilience contract
- When `GET /api/visualizer/sources` fails, `#vz-stage` must show an explicit fallback message.
- Fallback state must not remain in skeleton copy (`Lade Quellen`).

## Playwright dependency contract
- Python e2e module `tests/e2e/test_ui_workflow.py` must use `pytest.importorskip("playwright.sync_api")`.
- If Playwright is unavailable, suite behavior is deterministic:
  - e2e module is skipped (not failed)
  - healthcheck reports `e2e.mode=skip_python_e2e`
- If Playwright is available, healthcheck reports `e2e.mode=full`.
