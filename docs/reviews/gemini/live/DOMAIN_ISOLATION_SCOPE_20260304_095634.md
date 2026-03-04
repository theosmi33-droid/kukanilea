# Domain Isolation & Scope Report (2026-03-04)

## Overview
Worker C hat die Isolation der Domains Dashboard, Upload, Messenger und Chatbot geprüft. Für alle Domains wurden Scope Requests und Patches für Shared-Core-Berührungen erzeugt.

## Domain: dashboard
- **Overlap Status:** OVERLAP DETECTED
- **Shared Core Touched:** `app/templates/layout.html`, `app/__init__.py`, `app/core/logic.py`, `app/web.py`
- **Scope Request:** `docs/scope_requests/dashboard_20260304_095634.md`
- **Patch Path:** `docs/scope_requests/patches/dashboard_20260304_095634.patch`
- **Nächster Schritt:** Review des Patches und Freigabe für Core-Integration.

## Domain: upload
- **Overlap Status:** OVERLAP DETECTED
- **Shared Core Touched:** `app/__init__.py`, `app/templates/layout.html`
- **Scope Request:** `docs/scope_requests/upload_20260304_095634.md`
- **Patch Path:** `docs/scope_requests/patches/upload_20260304_095634.patch`
- **Nächster Schritt:** Abgleich mit Dashboard-Layout Änderungen (potenzieller Konflikt).

## Domain: messenger
- **Overlap Status:** OVERLAP DETECTED
- **Shared Core Touched:** `app/__init__.py`, `app/templates/layout.html`
- **Scope Request:** `docs/scope_requests/messenger_20260304_095634.md`
- **Patch Path:** `docs/scope_requests/patches/messenger_20260304_095634.patch`
- **Nächster Schritt:** Validierung der Messenger-Agent Integration in `app/__init__.py`.

## Domain: floating-widget-chatbot
- **Overlap Status:** OVERLAP DETECTED
- **Shared Core Touched:** `app/__init__.py`
- **Scope Request:** `docs/scope_requests/floating-widget-chatbot_20260304_095635.md`
- **Patch Path:** `docs/scope_requests/patches/floating-widget-chatbot_20260304_095635.patch`
- **Nächster Schritt:** Finaler Check der Chatbot-API Registrierung im Core.

## Zusammenfassung
Alle Domains weisen Berührungen mit dem Shared Core auf (hauptsächlich `app/__init__.py` und `app/templates/layout.html`). Die entsprechenden Patches wurden isoliert und stehen für den Merge-Prozess bereit.
