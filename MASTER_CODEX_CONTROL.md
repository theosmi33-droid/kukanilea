# MASTER_CODEX_CONTROL

Kanonische Steuerungsanweisung für Codex-Läufe in KUKANILEA.

## Zielzustand
Ein Agent-Lauf ist nur dann merge-fähig, wenn er **deterministisch** innerhalb eines klaren Vertrags arbeitet:

- kein Merge ohne gemeinsamen Tool-Contract,
- kein Merge ohne Scope-Kontrolle,
- kein Merge ohne Preflight,
- kein Merge ohne Test- und Evidence-Nachweis.

## Nicht verhandelbare Regeln (Hard Requirements)
1. Arbeitsbasis ist immer `origin/main`.
2. Domain-Worker arbeiten ausschließlich innerhalb ihrer Allowlist.
3. Shared-Core-Dateien sind in Domain-Lanes tabu (`app/web.py`, `app/core/logic.py`, `app/__init__.py`, `app/db.py`).
4. Bei Shared-Core-Bedarf muss der Worker exakt `CROSS_DOMAIN_WARNING` ausgeben und stoppen.
5. Scope-Dokumente, Overlap-Checker und Shared-Contracts dürfen nicht implizit in Domain-PRs geändert werden.
6. Harmonisierung über mehrere Tools läuft nur über eine separate Integrations-Lane.
7. Jeder Lauf ist vor Abgabe durch vier Gates zu validieren:
   - Domain-Overlap,
   - Tool-Contract-Tests,
   - Release-Conductor-Preflight,
   - PR-Quality-Guard.

## Verbindlicher Tool-Contract
Jedes Tool muss konsistent denselben Vertragsrahmen liefern:

- `GET /api/<tool>/summary`
- `GET /api/<tool>/health`
- identische Pflichtfelder
- kompatible `payload_contracts`

Ohne vollständigen Contract gilt der Lauf als nicht merge-fähig.

## Operative Reihenfolge
1. Umgebung normieren (`origin`, `main`, Revision).
2. Scope-Dokumente und Overlap-Checker synchronisieren.
3. Runtime-/Test-Basis stabilisieren (`.python-version`, `pytest`, `flask`, Healthcheck).
4. Tool-Contract-Matrix für alle 11 Tools vereinheitlichen.
5. Release-Conductor-Preflight verpflichtend vor jedem PR.
6. Domain-PRs klein halten; Harmonisierung nur separat in Integrations-PRs.

## Master Prompt (Domain-Lane)
```text
Du arbeitest ausschließlich gegen den aktuellen Stand von origin/main.

Nicht verhandelbare Regeln:
1. Arbeite nur in der erlaubten Allowlist des zugewiesenen Tools.
2. Wenn du shared core berühren musst (z. B. app/web.py, app/core/logic.py, app/__init__.py, app/db.py), gib exakt CROSS_DOMAIN_WARNING aus und stoppe.
3. Ändere keine Scope-Dokumente, keine Overlap-Checker und keine Shared-Contracts implizit in einem Domain-PR.
4. Jeder Change muss denselben Tool-Contract respektieren:
   - /api/<tool>/summary
   - /api/<tool>/health
   - identische Pflichtfelder
   - kompatible payload_contracts
5. Vor Abschluss MUSS laufen:
   - python scripts/dev/check_domain_overlap.py --reiter <tool> --files <changed_files>
   - relevante Contract-Tests
   - bash scripts/dev/pr_quality_guard.sh --ci
   - bash scripts/dev/release_conductor_preflight.sh
6. Wenn pytest, flask, origin, main oder eine gültige Revision fehlen, stoppe und klassifiziere den Lauf als BLOCKED_ENVIRONMENT.
7. Keine stillen Cross-Tool-Änderungen. Wenn Harmonisierung mehr als ein Tool betrifft, erstelle einen separaten INTEGRATION_CONTRACT_REQUEST und stoppe.
8. Ergebnisformat:
   - Scope In
   - Scope Out
   - Changed Files
   - Contract Impact
   - Tests
   - Guard Result
   - Risks
   - PR Readiness
```

## Master Prompt (Integrations-Lane)
```text
Du bist Integration Conductor für KUKANILEA.
Dein Auftrag ist nicht Feature-Entwicklung, sondern Harmonisierung zwischen Tools.

Pflichten:
1. Vergleiche alle Tool-Contracts und identifiziere Feld-Drift, Endpoint-Drift, Confirm-Flow-Drift und Health/Summary-Drift.
2. Liefere nur einen kleinen PR gegen main, der gemeinsame Verträge oder gemeinsame Tests vereinheitlicht.
3. Keine Domain-spezifische Runtime-Logik ändern, außer zur Durchsetzung eines bereits definierten gemeinsamen Vertrags.
4. Wenn Scope-Doku und Overlap-Checker nicht übereinstimmen, behandle das als Governance-Bug und fixe zuerst die Governance.
5. Ein Harmonisierungslauf gilt nur als PASS, wenn:
   - alle betroffenen Contract-Tests grün sind,
   - Overlap-Regeln konsistent sind,
   - Release-Conductor-Preflight grün oder bewusst WARN-only ist,
   - keine impliziten Shared-Core-Nebenänderungen enthalten sind.
```

## Fail-Codes
- `PASS`
- `BLOCKED_ENVIRONMENT`
- `CROSS_DOMAIN_WARNING`
- `SCOPE_DRIFT`
- `CONTRACT_DRIFT`
- `UX_POLICY_DRIFT`
- `PR_NOT_MERGEABLE`
