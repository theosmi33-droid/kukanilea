# CI/QA Test-Matrix (Navigation/Projects/Chat/Security)

Stand: 2026-03-04

| Bereich | Testdatei | Status vor Anpassung | Klassifikation | Änderung | Erwartung nach Anpassung |
|---|---|---|---|---|---|
| Navigation | `tests/integration/test_navigation_smoke.py` | Fail (sporadisch bei veralteten HX-Erwartungen / Fehlerseiten unerkannt) | Veralteter Test-Contract | Zusätzliche robuste Assertions: kein `traceback`, kein `Internal Server Error` bei 200-Antworten. | Pass stabil gegen aktuellen Full-Page-Contract |
| Projects | `tests/test_projects_page.py` | Fail (fragile Text-Checks auf `kanban`/`project hub`) | Veralteter Test gegen alte UI-Texte | Ersetzt durch Contract-Checks auf Kern-Elemente (`#project-hub`, `#kanban`) + kein Fehlerbanner. HX-Request explizit als Full-Page-Contract abgesichert. | Pass stabil bei UI-Textänderungen |
| Chat | `tests/test_chat_widget_compat.py` | Fail (fragile Exakt-Assertion auf Antworttext) | Veralteter Test gegen alte Formulierung | Exakt-Text entfernt; stattdessen Assertions auf `ok`, `requires_confirm`, `pending_id`, und `status`-Semantik (`ausgeführt`). | Pass stabil bei Copy-Änderungen |
| Security | `tests/security/test_chatbot_confirm_guardrails.py`, `tests/security/test_confirm_and_injection_gates.py` | Erwartet grün | Echte Guardrail-Verifikation (kein Hinweis auf Regression) | Keine Änderung nötig; bestehende Assertions bereits contract-nah. | Weiterhin Pass |

## Kurzklassifikation CI-Fehlerbild
- **Echte Regression:** keine in den hier bearbeiteten Bereichen identifiziert.
- **Veraltete Tests:** Navigation/Projects/Chat (Copy-/Markup-drift bei unverändertem fachlichem Contract).
- **Flaky/Infrastruktur:** lokale Ausführung in dieser Umgebung durch fehlende Python-Abhängigkeiten blockiert (kein Paketzugriff via Proxy).
