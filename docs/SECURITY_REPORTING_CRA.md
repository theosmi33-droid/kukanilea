# CRA Security Reporting Runbook (EU Cyber Resilience Act)

Dieses Dokument definiert den Prozess zur Meldung von ausgenutzten Schwachstellen und schwerwiegenden Sicherheitsvorfällen gemäß den Anforderungen des EU CRA (Phase 1, ab 11.09.2026).

## 1. Meldefristen (Reporting Timeline)

| Phase | Ziel | Frist (nach Kenntnisnahme) | Empfänger |
|-------|------|---------------------------|-----------|
| **Early Warning** | Kurzinformation über den Vorfall | 24 Stunden | ENISA / Nationale Behörde |
| **Full Notification** | Detaillierter Bericht & erste Bewertung | 72 Stunden | ENISA / Nationale Behörde |
| **Final Report** | Abschlussbericht & Korrekturmaßnahmen | 14 Tage (nach Behebung) | ENISA / Nationale Behörde |

## 2. Vorfalleinstufung (Severity)

*   **Critical:** Ausnutzung führt zu unbefugtem Zugriff auf Kundendaten oder Systemübernahme.
*   **Severe:** Massive Beeinträchtigung der Verfügbarkeit oder Integrität der Kerndienste.

## 3. Templates

### 24h Early Warning Template
```text
Subject: Early Warning - Security Incident - Kukanilea
To: [ENISA/National Authority]

1. Product: Kukanilea (Handwerker-CRM/ERP)
2. Discovery Time: [YYYY-MM-DD HH:MM]
3. Incident Type: [Exploited Vulnerability / Severe Incident]
4. Initial Impact: [Brief description of affected components]
5. Contact: [Security Officer Name]
```

## 4. Verantwortlichkeiten

*   **Release Captain:** Koordination der Beweissicherung.
*   **Lead Architect:** Technische Analyse und Fix-Verifizierung.
*   **Compliance Officer:** Formale Meldung an Behörden.
