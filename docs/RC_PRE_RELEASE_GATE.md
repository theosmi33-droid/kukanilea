# RC-/Pre-Release-Gate (kleinster belastbarer Satz)

Ziel: Für RC/Pre-Release eine kompakte, reproduzierbare **Go/No-Go**-Entscheidung auf current `main`.

## Pflichtgates (müssen grün sein)

1. **Guardrails** (Zero-CDN, White-Mode, lokale Assets):
   - `python scripts/ops/verify_guardrails.py`
2. **Ops-Healthcheck** (Baseline inkl. Sicherheits-/Betriebschecks):
   - `bash scripts/ops/healthcheck.sh`

Diese beiden Gates sind **hartes No-Go** bei Fehlern.

## Optionale, scope-abhängige Zusatzgates

Nur wenn das Arbeitspaket sie berührt:

- **Relevante Pytests**: `pytest -q [nur relevante Tests]`
- **Ruff auf betroffene Dateien**: `ruff check [betroffene Dateien]`

## Akzeptiertes Restrisiko

Ein Release kann als **GO** gelten, wenn beide Pflichtgates grün sind und nur folgende Restrisiken offen bleiben:

- Keine zusätzlichen, nicht betroffenen Testbereiche wurden ausgeführt.
- Optionale Lint-Checks wurden bewusst auf den Scope begrenzt.

Nicht akzeptiert (immer **NO-GO**):

- Fail in Guardrails oder Healthcheck.
- Security-/Policy-Regressionen oder abgeschwächte Schutzmechanismen.

## Reproduzierbare Anwendung

Einzeln:

```bash
python scripts/ops/verify_guardrails.py
bash scripts/ops/healthcheck.sh
```

Automatisiert (minimal):

```bash
scripts/ops/rc_pre_release_gate.sh
```

Hinweis: Das Script nutzt intern `healthcheck.sh --skip-pytest` und erwartet scope-spezifische Pytests separat über `RC_PYTEST_TARGETS`.

Mit scope-spezifischen Zusatzchecks:

```bash
RC_PYTEST_TARGETS="tests/test_guardrails.py" \
RC_RUFF_TARGETS="scripts/ops/rc_pre_release_gate.sh" \
scripts/ops/rc_pre_release_gate.sh
```

## Entscheidungsregel (Go/No-Go)

- **GO**: Pflichtgates PASS.
- **NO-GO**: Mindestens ein Pflichtgate FAIL (Exit-Code `3`).
