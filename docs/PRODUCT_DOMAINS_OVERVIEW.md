# KUKANILEA Product Domains Overview

Single Source of Truth fuer die 11 Domaenen-Projekte.

## 0) Ziel des Dokuments
KUKANILEA wird in 11 Domaenen aufgeteilt. Jede Domaene arbeitet isoliert im eigenen Worktree und liefert klar definierte Funktionen, Schnittstellen und Abnahmeziele.

Produktziele:
- Local-First
- Offline-faehig
- Security-Hardened
- Teamfaehig ohne Scope-Chaos

## 1) Globales Operating Model (verbindlich)

### 1.1 Domain Exclusivity
- Arbeit nur im zugewiesenen Worktree.
- Vor jeder Aenderung: Overlap-Check.
- Bei Not-Owned-Datei: STOP + Scope-Request.

Overlap-Check:
```bash
python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/check_domain_overlap.py --reiter <reiter> --files <file> --json
```

### 1.2 Cross-Domain-Files (nur mit Freigabe)
Bei Bedarf an Aenderungen hier gilt immer `CROSS_DOMAIN_WARNING` + Scope-Request:
- `app/web.py`
- `app/db.py`
- `app/core/logic.py`
- globale Shell/Layout/Sidebar/Auth/Policy-Dateien

### 1.3 Offline-Dogma
- Kernworkflows muessen ohne Internet nutzbar sein.
- Externe Integrationen sind opt-in und cachen lokal.
- Bei Offline klarer Degrade-Status statt stiller Fehler.

### 1.4 Audit und Confirm-Gates
- Zustandsaenderungen sind auditierbar (wer/was/wann/wo).
- Riskante Aktionen brauchen Confirm-Gate (Delete, Restore, Send, Rotation, Restore).

### 1.5 Performance-Ziele
- UI Interaktion: Ziel <100ms (wahrgenommen)
- Serverantwort: Ziel <200ms
- Upload/OCR: Ziel 3s/Seite (10 Seiten <30s)
- Visualizer First Paint: Ziel <2s
- Chatbot einfache Antworten: Ziel <2s lokal

## 2) Big Picture Datenfluesse

### 2.1 Dokumentfluss
1. Eingang via Upload oder Mail/Messenger-Anhang
2. ClamAV-Scan, OCR, Metadaten
3. RAG Sync (sqlite-vec)
4. Verknuepfung mit CRM/Projekt, ggf. Task/Kalender
5. Darstellung im Visualizer

### 2.2 Kommunikationsfluss
- Email/Messenger -> lokales Archiv -> CRM-Match -> optional Task/Kalender/Dokument

### 2.3 Work-Management-Fluss
- Projekte (Kanban) <-> Aufgaben <-> Zeiterfassung

### 2.4 Steuerungsfluss
- Einstellungen definieren globale Regeln, Rechte, Sync, Backup
- Dashboard zeigt Health/Queue/Anomalien

### 2.5 Assistenzfluss
- Floating Chatbot steuert Skills ueber alle Domaenen
- Schreibende Aktionen nur mit Confirm-Gate

## 3) Worktree-/Branch-Zuordnung
1. Dashboard: `/Users/gensuminguyen/Kukanilea/worktrees/dashboard` -> `codex/dashboard`
2. Upload: `/Users/gensuminguyen/Kukanilea/worktrees/upload` -> `codex/upload`
3. Emailpostfach: `/Users/gensuminguyen/Kukanilea/worktrees/emailpostfach` -> `codex/emailpostfach`
4. Messenger: `/Users/gensuminguyen/Kukanilea/worktrees/messenger` -> `codex/messenger`
5. Kalender: `/Users/gensuminguyen/Kukanilea/worktrees/kalender` -> `codex/kalender`
6. Aufgaben: `/Users/gensuminguyen/Kukanilea/worktrees/aufgaben` -> `codex/aufgaben`
7. Zeiterfassung: `/Users/gensuminguyen/Kukanilea/worktrees/zeiterfassung` -> `codex/zeiterfassung`
8. Projekte: `/Users/gensuminguyen/Kukanilea/worktrees/projekte` -> `codex/projekte`
9. Visualizer: `/Users/gensuminguyen/Kukanilea/worktrees/excel-docs-visualizer` -> `codex/excel-docs-visualizer`
10. Einstellungen: `/Users/gensuminguyen/Kukanilea/worktrees/einstellungen` -> `codex/einstellungen`
11. Floating Widget: `/Users/gensuminguyen/Kukanilea/worktrees/floating-widget-chatbot` -> `codex/floating-widget-chatbot`

## 4) Die 11 Domaenen (kompakt und eindeutig)

### 4.1 Dashboard
Zweck: Kompakte Kommandozentrale.
- Widgets: Wetter, neue Mails, neue Messenger-Nachrichten, offene Tasks, Projektstatus, naechste Termine, System-Health.
- Echtzeit via HTMX Polling/SSE.
- Offline: lokale Widgets immer sichtbar, Wetter aus Cache.

### 4.2 Upload
Zweck: Zentrale Ingestion-Engine.
- Drag-and-drop, OCR, Metadaten, ClamAV, RAG Sync.
- Auto-Learning aus Korrekturen per Layout-Hash.
- Ziel: 10 Seiten <30s, EICAR blockieren, audit loggen.

### 4.3 Emailpostfach
Zweck: Lokaler Multi-Account Mail-Client.
- IMAP Sync, lokales Archiv, Anhaenge -> Upload.
- CRM-Match, KI-Antwortentwuerfe lokal, Mail->Task, Mail->Termin.

### 4.4 Messenger
Zweck: Externe + interne Kommunikation in einer Drehscheibe.
- Provider-Connectoren, internes Chat-System.
- Medien/Anhaenge -> Upload, Chat->Task/Termin.
- Offline: intern immer, extern degrade.

### 4.5 Kalender
Zweck: Einheitliche Termin- und Fristenverwaltung.
- Termine aus Dokumenten, Mail, Messenger.
- Manuelle Eintraege, Erinnerungen, ICS Export.
- Fristen koennen Tasks erzeugen.

### 4.6 Aufgaben
Zweck: Team-Aufgabenfluss.
- Erstellen, zuweisen, annehmen/ablehnen, Status-Workflow.
- Benachrichtigung lokal, Verknuepfung zu Projekten/Zeiten.

### 4.7 Zeiterfassung
Zweck: Mitarbeitertracking + Admin-Reporting.
- Start/Stop, manuelle Buchungen, Team-Ansicht, Charts, CSV Export.
- Verknuepfung mit Aufgaben/Projekten.

### 4.8 Projekte
Zweck: Kanban-Hub fuer Projektarbeit.
- Boards/Spalten/Karten, Kommentare, Aktivitaetslog.
- Verknuepfung mit CRM, Aufgaben, Zeiten, Dokumenten.

### 4.9 Visualizer
Zweck: Dokumente schnell verstehen.
- Multi-Format Rendering, KI-Zusammenfassung, Diagramme, Export.
- Ergebnis in Projekte ablegen.

### 4.10 Einstellungen
Zweck: Admin-Zentrale.
- User/Rollen, Tenants, Lizenz, Mesh, Branding, Backup/Restore.
- Klare Rechte-Trennung (Admin vs Nutzer).

### 4.11 Floating Widget Chatbot
Zweck: Universeller Assistent ueber alle Module.
- Kontextbewusster Chat, Skills, ReAct, Confirm-Gates.
- Minimierbar, Hintergrundbereit, leichte lokale Modelle + lokaler Fallback.

## 5) Definition of Done (pro Domaene)
Jede Domaene gilt nur als abgeschlossen, wenn alle Punkte erfuellt sind:
- Scope eingehalten (kein unfreigegebenes Cross-Edit)
- Relevante Tests gruen
- Offline-Degrade klar und sichtbar
- Audit-Ereignisse fuer kritische Aktionen vorhanden
- Confirm-Gates fuer riskante Aktionen vorhanden
- Performance-Ziel fuer die Domaene mindestens gemessen
- Domaenenstatus in Shared Memory aktualisiert
- Kurze User-Doku/Release Note angelegt

## 6) Praktische Nutzung
- Dieses Dokument ist verbindliche Referenz fuer Devs, Codex und Gemini.
- Bei Konflikten entscheidet zuerst Scope-Regel, dann Security, dann Feature-Wunsch.
- Neue Teammitglieder starten immer mit diesem Dokument.
