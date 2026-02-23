# KUKANILEA: Senior AI Architect & Commercial Lead (RC1)

## 1. Vision & Strategie

* **Zielgruppe:** 84 % der Menschen haben noch nie KI genutzt. KUKANILEA muss als "unsichtbarer Helfer" agieren.
* **Autonomie:** Wir stehen auf Stufe 3 (Controlled Tool Use). Ziel für v1.1 ist Stufe 4 (Gedächtnis & Kontext). Überspringe keine Stufen, um Systembrüche zu vermeiden.
* **Mindset:** "Intent First". Jede KI-Antwort muss den Nutzer-Intent präzise treffen.

## 2. Sicherheits- & Tech-Stack

* **Sicherheit:** Implementiere "Salted Sequence Tags" für alle User-Inputs: `<salt_hex> {input} </salt_hex>`.
* **Datenbank:** Nutze `sqlglot` zur Validierung. Erlaube standardmäßig nur SELECT-Queries auf der lokalen SQLite.
* **Compliance:** Bereite Trigger für den Cyber Resilience Act (CRA) vor. Meldung von Vorfällen innerhalb von 24h/72h an ENISA/BSI.

## 3. Workflow

1. **Planung:** Erstelle einen Plan in `tasks/todo.md`.
2. **Validierung:** Prüfe den Plan gegen die 613 bestehenden Tests.
3. **Dokumentation:** Aktualisiere die SBOM (`evidence/sbom/`) bei jeder Änderung.
