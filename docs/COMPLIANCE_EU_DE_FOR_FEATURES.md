# COMPLIANCE_EU_DE_FOR_FEATURES

## Scope
Dieses Dokument operationalisiert EU/DE-Compliance für geplante Feature-Bereiche in KUKANILEA. Fokus: umsetzbare Mindestanforderungen, Prüf-Checklisten und Evidence-Artefakte für Release-Gates.

## A) Voice/Telephony AI
### What triggers compliance
- Verarbeitung personenbezogener Daten aus Anrufen/Transkripten.
- Verarbeitung von Kommunikations- oder Verkehrsdaten im Telekom-Kontext.

### Minimum required UX text/consent
- Klare Disclosure vor oder zu Beginn der Interaktion: AI-Unterstützung aktiv.
- Hinweis auf Zweck der Verarbeitung (z. B. Terminierung, Triage, Dokumentation).
- Sofern erforderlich: explizite Einwilligung für Aufzeichnung/Transkription.

### Data minimisation
- Default ohne Volltranskript-Speicherung, falls nicht nötig.
- Speicherung nur zweckgebundener Felder (z. B. Intent, Callback, Ticket-ID).

### Retention
- Kurze, dokumentierte Aufbewahrungsfristen je Datentyp.
- Automatisierte Löschung/Anonymisierung nach Frist.

### Audit evidence
- Consent-/Disclosure-Event mit Zeitstempel und Request-ID.
- Datenfluss-Dokumentation (welcher Provider, welche Datenkategorien).
- Runbook: Incident/Deletion Request.

## B) Time Tracking / HR
### What triggers compliance
- Erfassung von Arbeitszeit-/Aktivitätsdaten inkl. Personenbezug.
- Exporte in Payroll/Buchhaltungssysteme.

### Minimum required UX text/consent
- Transparente Information über erfasste Felder, Zweck und Exportziele.
- Sichtbare Korrektur-/Freigabefunktionen für Zeitbuchungen.

### Data minimisation
- Keine Erfassung irrelevanter Zusatzdaten.
- Rollenbasierter Zugriff auf sensible HR-/Zeitdaten.

### Retention
- Dokumentierte Aufbewahrungs- und Korrekturregeln.
- Nachvollziehbare Historie bei Änderungen (Audit Trail).

### Audit evidence
- Export-Protokolle mit Hash/ID, Zeitstempel und Ausführendem.
- Testnachweis für Export-Integrität (CSV/PDF/DATEV).
- Dokumentierte Rundungs-/Regel-Policy (falls genutzt).

## C) Workflow Approvals and Audit Trails
### What triggers compliance
- Freigaben für rechtlich/operativ kritische Prozesse.
- Entscheidungen mit Nachweispflicht.

### Minimum required UX text/consent
- Sichtbarer Freigabestatus, Verantwortlicher und Zeitpunkt.
- Klare Begründung bei Ablehnung/Änderung.

### Data minimisation
- Nur entscheidungsrelevante Daten im Freigabeprotokoll.
- Keine unnötigen Freitext-PII in Systemevents.

### Retention
- Versionierte Historie für Freigabeobjekte.
- Archivierungsregel mit Zugriffsschutz.

### Audit evidence
- Versionen + Statuswechsel + Verantwortliche + Request-ID.
- Dashboard über offene/überfällige Freigaben.

## D) AI Transparency and Assistant UX
### What triggers compliance
- Interaktion Nutzer <-> AI-System.
- AI-generierte Inhalte/Empfehlungen mit operativer Relevanz.

### Minimum required UX text/consent
- AI-Disclosure in UI (Assistant ist AI-basiert).
- Kennzeichnung, wenn Inhalte AI-generiert sind (wo anwendbar).

### Data minimisation
- Keine unnötigen Prompt-/Konversationsinhalte in Audits.
- Reduzierte, redaktierte Logs mit technischen IDs statt Klardaten.

### Retention
- Kurze Retention für Diagnose-Logs.
- Long-term-Speicherung nur für freigegebene Artefakte.

### Audit evidence
- Event-Logs für Tool-Entscheidungen (`allowed/denied/confirmed`).
- Nachweis von Fallback-Verhalten ohne UI-Blockade.

## Release Checklist (Operational)
- [ ] Disclosure-Texte in UI vorhanden und getestet.
- [ ] Consent-/Rechtsgrundlagen-Fallunterscheidung dokumentiert.
- [ ] Retention-Policy pro Datentyp dokumentiert und technisch hinterlegt.
- [ ] Audit-Evidence je Featureklasse (Logs, Screenshots, Testläufe) abgelegt.
- [ ] Exportintegrität und Freigabehistorie reproduzierbar verifiziert.

## Sources
- GDPR Art. 6 (Lawfulness): [EUR-Lex Art. 6](https://eur-lex.europa.eu/eli/reg/2016/679/art_6/oj/eng)
- Telekom/Datenschutz (DE): [Bundesnetzagentur TTDSG/Datenschutz](https://www.bundesnetzagentur.de/DE/Vportal/TK/Datenschutz/artikel.html)
- Working Time Directive overview: [EU-OSHA Directive 2003/88/EC](https://osha.europa.eu/en/legislation/directives/directive-2003-88-ec)
- Working Time Directive legal text: [EUR-Lex 2003/88/EC](https://eur-lex.europa.eu/eli/dir/2003/88/oj)
