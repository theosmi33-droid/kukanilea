# KUKANILEA - Engineering Prompts (Domänen 1-10)

Status: Domäne 11 (Floating Widget Chatbot) läuft bereits und ist in diesem Paket explizit ausgenommen.

## 0) Ziel
Dieses Dokument ist die verbindliche Arbeitsgrundlage für die Domänen 1-10. Es stellt sicher, dass alle Teams konsistent entwickeln, ohne Cross-Domain-Chaos.

## 1) Verbindliche Regeln
- Domain Exclusivity: Änderungen nur im zugewiesenen Worktree und Scope.
- Overlap-Check vor jeder Änderung:
  `python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/check_domain_overlap.py --reiter <projekt> --files <datei> --json`
- Shared-Core-Dateien nur mit Freigabe (Scope-Request + Review):
  - `app/web.py`
  - `app/db.py`
  - `app/core/logic.py`
  - globale Layout/Auth/Policy-Dateien
- Offline-First: Kernworkflows müssen ohne Internet nutzbar bleiben.
- Audit + Confirm-Gates: schreibende oder riskante Aktionen nur mit Audit-Log und expliziter Bestätigung.
- SLA-Ziele:
  - UI-Interaktionen: < 100 ms
  - API-Antworten: < 200 ms
  - OCR: ~3 s pro Seite
  - Visualizer: erste Seite < 2 s
- UI-Standard: White-Mode, 8pt-Grid, keine externen CDN-Fonts.

## 2) Domänen mit Scope und Definition of Done

### Projekt 1: Dashboard
- Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/dashboard`
- Zweck: Kompakte Kommandozentrale mit Live-Widgets.
- Muss enthalten:
  - Wetter (Cache), neue Nachrichten, offene Aufgaben, neue E-Mails, Projektstatus, nächste Termine, System-Health.
  - HTMX-Polling oder SSE für Aktualisierung.
- DoD:
  - Alle Widgets mit echten Daten.
  - Klare Offline-Degrade-Hinweise.
  - Warnungen bei Anomalien funktionieren.

### Projekt 2: Upload
- Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/upload`
- Zweck: OCR-Ingestion mit Auto-Learning und Virenscan.
- Muss enthalten:
  - Drag-and-drop + Progress.
  - ClamAV Pflichtscan vor Verarbeitung.
  - OCR + Metadaten + Korrekturlernen via `layout_hash`.
  - RAG-Sync in sqlite-vec.
- DoD:
  - 10 Seiten < 30 s.
  - EICAR wird blockiert.
  - Korrekturen werden bei ähnlichem Layout wiederverwendet.

### Projekt 3: Emailpostfach
- Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/emailpostfach`
- Zweck: Lokaler Multi-Account-Mail-Client mit Automationen.
- Muss enthalten:
  - IMAP-Sync, lokales Archiv, Attachments -> Upload.
  - CRM-Match über Absender.
  - Mail -> Aufgabe / Mail -> Termin.
  - Lokale KI-Antwortentwürfe.
- DoD:
  - Konto anlegen + Sync stabil.
  - Anhänge korrekt gescannt und übergeben.

### Projekt 4: Messenger
- Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/messenger`
- Zweck: Interne und externe Kommunikationsdrehscheibe.
- Muss enthalten:
  - Provider-Connectoren mit einheitlichem Interface.
  - Lokale Nachrichtenspeicherung, CRM-Link, Attachment -> Upload.
  - Nachricht -> Aufgabe/Termin.
- DoD:
  - Interner Chat stabil.
  - Mindestens ein externer Connector funktionsfähig.

### Projekt 5: Kalender
- Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/kalender`
- Zweck: Lokale Termin- und Fristensteuerung.
- Muss enthalten:
  - Manuelle Termine + Wiederholungen.
  - Terminquellen aus Upload, Mail und Messenger.
  - ICS-Export.
  - Erinnerungen und Frist -> Aufgabe.
- DoD:
  - Terminanlage und automatische Übernahme stabil.
  - ICS-Feed importierbar.

### Projekt 6: Aufgaben
- Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/aufgaben`
- Zweck: Team-Aufgaben mit klaren Zuständen.
- Muss enthalten:
  - Erstellen, zuweisen, annehmen, ablehnen, delegieren.
  - Status: Offen -> In Arbeit -> Erledigt/Ablehnt.
  - Lokale Benachrichtigungen.
- DoD:
  - Voller Aufgaben-Lebenszyklus testbar.
  - Integrationen mit Mail/Messenger/Projekten funktionieren.

### Projekt 7: Zeiterfassung
- Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/zeiterfassung`
- Zweck: Nutzertracking und Admin-Reporting.
- Muss enthalten:
  - Start/Stop und manuelle Einträge.
  - Ansichten Tag/Woche/Monat/Jahr.
  - Admin-Auswertung + CSV-Export (GoBD-konform).
- DoD:
  - Exporte korrekt.
  - Rechte sauber getrennt (Nutzer/Admin).

### Projekt 8: Projekte (Kanban)
- Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/projekte`
- Zweck: Projekt-Hub im Kanban-Stil.
- Muss enthalten:
  - Projekte, Spalten, Karten, Kommentare, Aktivitäten.
  - Drag-and-drop.
  - Verknüpfung zu CRM, Aufgaben, Zeiten und Dokumenten.
- DoD:
  - Board performant und stabil.
  - Aktivitäten vollständig nachvollziehbar.

### Projekt 9: Visualizer
- Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/excel-docs-visualizer`
- Zweck: Dokumente rendern, zusammenfassen, visualisieren.
- Muss enthalten:
  - PDF/Office/Bild/Text Darstellung.
  - Lokale KI-Zusammenfassung.
  - Diagramme aus strukturierten Daten.
- DoD:
  - Erste Seite < 2 s.
  - Zusammenfassung + Export stabil.

### Projekt 10: Einstellungen
- Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/einstellungen`
- Zweck: Admin-Zentrale für Governance.
- Muss enthalten:
  - Benutzer/Rollen, Tenants, Lizenz, Mesh, Branding, Backup/Restore.
  - Rechte-Trennung.
  - Confirm-Gates für kritische Aktionen.
- DoD:
  - Untermenüs stabil.
  - Kritische Flows abgesichert.

## 3) Integration zwischen den Domänen (Pflicht)
- Upload -> Kalender: Fristen und Termine aus Dokumenten.
- Upload -> Visualizer/Projekte: Dokumentverknüpfung.
- Email/Messenger -> Upload: Attachment-Ingestion.
- Email/Messenger -> Aufgaben/Kalender: schnelle Umwandlung.
- Aufgaben <-> Zeiterfassung: Aufwand direkt aus Task.
- Projekte <-> Aufgaben/Zeiten/Dokumente: Kanban als Hub.
- Einstellungen -> Alle: globale Regeln, Rollen, Lizenz, Mesh.

## 4) Ausführungsprotokoll pro Domäne
1. Scope lesen und lokale Änderungen planen.
2. Overlap-Check vor jedem Edit laufen lassen.
3. Änderungen klein halten und testbar liefern.
4. Relevante Tests ausführen.
5. Ergebnis in Scope-README dokumentieren.

## 5) Explizit ausgeschlossen in diesem Paket
- Domäne 11 (Floating Widget Chatbot): keine neuen Änderungen in diesem Integrationslauf.
