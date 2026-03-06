# MIA Eingangs-Guardrails (Untrusted Input Layer)

Diese Schicht behandelt **E-Mails, OCR-Texte, Chat-Nachrichten, Dateiinhalte, Markdown, Prompt-Dateien, Tickets und Logs** als untrusted input.

## Reihenfolge der Kontrollen

1. **Pre-Intent Guardrail** (`assess_untrusted_input`) vor Intent-Auflösung.
2. Klassische Pattern-Prüfungen (`detect_injection`, `validate_prompt`) als zusätzliche Ebene.
3. **Pre-Execution Guardrail** in `/api/ai/execute` auf Skill + Payload.
4. Confirm-Gate bleibt aktiv für Write/High-Risk Aktionen.
5. Audit-Einträge für `*_guardrail_blocked`, `*_guardrail_warning`, `chat_confirm_required`.

## Entscheidungsmodell

- `allow`: Keine kritischen Signale erkannt.
- `allow_with_warning`: Verdächtige, aber evtl. legitime Inhalte (z. B. Angriffsbeschreibung im Fachtext).
- `route_to_review`: Prompt-/Policy-Manipulationssignale, keine direkte Ausführung.
- `block`: Exfiltration, destruktive Ausführung oder FS/Netzwerk-Angriffsindikatoren.

## Erkannte Muster (Auszug)

- Instruction override: `ignore previous instructions`, policy override.
- Tool escalation: direkte Shell/Subprocess/Tool-Ausführungsanforderungen.
- Exfiltration: `send data externally`, Webhook/Remote-Indikatoren.
- Rolle-Konfusion: `you are now system/admin/root`.
- Hidden directives: Prompt-/System-Blöcke in Markdown/OCR.
- Obfuscation: URL/HTML Decode + Base64 best-effort.

## Zusammenspiel mit Confirm-Gates und Audit

- Guardrails entscheiden, **ob** ein Input weiter verarbeitet wird.
- Confirm-Gates entscheiden bei erlaubten Inputs, **ob** Ausführung explizite Bestätigung benötigt.
- Blockierte oder zur Prüfung geroutete Inputs erzeugen Audit-Spuren, statt stiller Failover-Execution.

## Safe Fallback

- Block/Review führt zu explizitem API-Fehler (`injection_blocked`) bzw. sicherem Stopp.
- Keine direkte Tool-Auswahl aus manipulativem untrusted Text.
- Keine freie Shell/Subprocess-Ausführung aus untrusted Content.

## Verbleibende Risiken

- Stark kontextabhängige Fachtexte können weiterhin `route_to_review` triggern (False Positives).
- Sehr stark verschleierte Payloads (mehrstufige Kodierung) werden nur best-effort erkannt.
- Semantic-Angriffe ohne klare Pattern bleiben ein Rest-Risiko und werden über Confirm-Gate + Audit mitigiert.
