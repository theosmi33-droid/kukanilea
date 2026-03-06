# Guardrail-Abgrenzung: statisch vs. Runtime

## 1) Statische Repo-Guardrails
Die statische Schicht läuft als Repo-Scan (`scripts/ops/verify_guardrails.py`) und verhindert, dass prompt-injectionartige Kontrollphrasen unkontrolliert in produktiven Laufzeitpfaden landen.

- Scan auf Kontrollphrasen außerhalb der Allowlist.
- Absicherung von HTMX-Confirm-Gates.
- CDN-Policy-Prüfung.

Diese Schicht wirkt **vor Deployment** und schützt die Codebasis.

## 2) Runtime-Guardrails (MIA-Router)
Die Runtime-Schicht läuft im `ManagerAgent` zur Laufzeit in zwei Stufen:

1. **pre_intent**: Guard-Entscheidung vor Intent-Erkennung.
2. **pre_execution**: Guard-Entscheidung nach Routing, vor Action-Ausführung.

Entscheidungsmodell:

- `allow`
- `allow_with_warning`
- `block`
- `route_to_review`

Sicherheitsprinzipien:

- Untrusted Content darf keine direkte Action-Ausführung erzwingen.
- Pattern-Erkennung plus Normalisierung (`normalize_untrusted_input`).
- Safe Fallback (`safe_follow_up` / `safe_fallback`) statt blindem Ausführen.
- Audit-Event bei Block/Review/Warnung.
- Keine Halluzinations-Toolwahl (nur registrierte Actions werden geroutet).
