# Security and Escalation

## Security Baseline
- No PII in event payloads, logs, or telemetry.
- No secrets in plain text persistence.
- `subprocess` calls must use list argv, `shell=False`, explicit timeout.
- Token/code/hash comparisons must use `secrets.compare_digest()`.
- OCR/Mail text must be redacted before persistence.

## Escalation Path
1. Sofortkontakt
- Bei kritischem Security-/Compliance-Risiko sofort Team informieren und PR/Issue mit `critical` label markieren.

2. 2h-Regel
- Wenn nach 2 Stunden keine sichere Loesung klar ist: Pflicht-Meeting (Tech Lead + Product + Umsetzer).

3. Merge-Sperre
- Kritische Findings blockieren Merge bis dokumentierter Fix + Testnachweis vorliegt.

## Incident-Minimum
- Was ist passiert?
- Betroffener Scope (Tenant/Feature)
- Risikoabschaetzung
- Sofortmassnahmen
- Dauerhafte Massnahme + Tests
