# KUKANILEA Fleet Commander: Multi-Domain Setup

Dieses Dokument dient als zentrale Referenz für die 11 spezialisierten Worktrees. Kopiere die jeweiligen Instruktionen in den Chat von **MIA Workspace Assistenz** in VS Code, wenn du in einem spezifischen Modul arbeitest.

## Globale Guardrails (Für alle Agenten)
1. **Domain Isolation:** Arbeite NUR in deinem zugewiesenen Pfad.
2. **Offline-First:** Keine Cloud-APIs (außer dieser Entwicklungshilfe). Nutze lokal Ollama.
3. **GoBD-Compliance:** Revisionssichere Logs via ISO-8601 UTC.
4. **Performance:** UI < 100ms, Server < 200ms.

---

## 1. Dashboard (The Command Center)
- **Pfad:** `/Users/gensuminguyen/Kukanilea/worktrees/dashboard`
- **Ziel:** Echtzeit-Visuelle Kontrolle von System-Health und Sync-Queues.
- **Master-Prompt:** "Transformiere die dashboard.html in eine Echtzeit-Leitzentrale. Integiere den ObserverAgent und visualisiere die API-Outbound-Queue. Nutze HTMX."

## 2. Upload & OCR (The Ingestion Engine)
- **Pfad:** `/Users/gensuminguyen/Kukanilea/worktrees/upload`
- **Ziel:** 100% Erkennung durch Auto-Learning.
- **Master-Prompt:** "Härte die upload_pipeline.py. Implementiere das OCR-Wisdom-Injection Protokoll."

## 3. Emailpostfach (Sovereign Mail)
- **Pfad:** `/Users/gensuminguyen/Kukanilea/worktrees/emailpostfach`
- **Ziel:** Lokales Mail-Archiv mit MIA-Entwürfen.

## 4. Messenger (Fleet Orchestrator)
- **Pfad:** `/Users/gensuminguyen/Kukanilea/worktrees/messenger`
- **Ziel:** ReAct-Logik und Multi-Agenten-Kollaboration.

## 5. Kalender (Strategic Scheduling)
- **Pfad:** `/Users/gensuminguyen/Kukanilea/worktrees/kalender`
- **Ziel:** Termin-Extraktion aus Dokumenten.

## 6. Aufgaben (Operation Engine)
- **Pfad:** `/Users/gensuminguyen/Kukanilea/worktrees/aufgaben`
- **Ziel:** Automatisierung von Hintergrund-Tasks.

## 7. Zeiterfassung (Revenue Protector)
- **Pfad:** `/Users/gensuminguyen/Kukanilea/worktrees/zeiterfassung`
- **Ziel:** Lückenlose Erfassung & GoBD-Export.

## 8. Projekte (The Project Hub)
- **Pfad:** `/Users/gensuminguyen/Kukanilea/worktrees/projekte`
- **Ziel:** Kanban-Board mit semantischem Gedächtnis.

## 9. Visualizer (The Forensic Eye)
- **Pfad:** `/Users/gensuminguyen/Kukanilea/worktrees/excel-docs-visualizer`
- **Ziel:** High-Performance Rendering (< 100ms).

## 10. Einstellungen (Governance & Identity)
- **Pfad:** `/Users/gensuminguyen/Kukanilea/worktrees/einstellungen`
- **Ziel:** RSA-Lizenzen, Mesh-Identität, Mandanten-Isolation.

## 11. Floating Widget (AI Companion)
- **Pfad:** `/Users/gensuminguyen/Kukanilea/worktrees/floating-widget-chatbot`
- **Ziel:** Globaler, kontextbewusster Chatbot über JS-Injection.
