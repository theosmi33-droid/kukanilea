# AI Orchestrator Hardening – 2026-03-05

## Scope
PR #312 wurde mit Fokus auf Robustheit und Security-Gates erweitert:

1. Deterministische Intent-Matrix (`read` / `write` / `unsafe`) mit klaren Regex-Regeln.
2. Verlässliche Antworten für Smalltalk (`Hallo`, `Test`, `Funktionierst du?`).
3. Striktes Confirm-Gating für write/unsafe Intents inklusive Audit Event.
4. Erweiterte Injection/Jailbreak-Erkennung mit negativen Security-Tests.
5. Tool-Summary-basierte Antwortpfade für `/dashboard`, `/tasks`, `/projects`.

## Implementierungsdetails
- `app/ai/intent_analyzer.py`
  - `classify_intent_risk()` eingeführt.
  - Deterministische Kategorisierung + Begründung (`reason`).
- `app/web.py`
  - Widget-Smalltalk-Shortcuts hinzugefügt.
  - Kontextbezogene Tool-Summary-Responses ergänzt.
  - Confirm-Gate nun auch bei `unsafe` zuverlässig aktiv.
  - Audit-Metadaten erweitert (`intent_type`, `reason`).
- `app/routes/messenger.py`
  - Confirm-Gate + Audit auch für `unsafe` Intents erzwungen.
- `app/security/gates.py`
  - Neue Patterns gegen Jailbreak-/Prompt-Injection-Varianten.
- `app/agents/orchestrator.py`
  - Deterministische Smalltalk-Preflight-Response vor Search-Fallback.

## Validation
- Pflicht-CI-Gate ausgeführt:
  - `pytest -q tests/test_chat_widget_compat.py tests/security/test_confirm_and_injection_gates.py`
- Zusätzliche zielgerichtete Tests:
  - Intent-Matrix
  - erweiterte Injection-Patterns
  - Orchestrator-Smalltalk

## Ergebnis
- Keine "Keine Treffer"-Antwort mehr für einfache Verfügbarkeitsfragen.
- Write-/Unsafe-Intents werden im Widget und Messenger strikt durch Confirm-Gate geführt.
- Injection-Erkennung deckt mehr Jailbreak-Vektoren ab.
