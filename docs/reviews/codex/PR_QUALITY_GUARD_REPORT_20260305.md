# PR Quality Guard Report — 2026-03-05

## Ziel
Absicherung gegen zu kleine / nicht belegte PRs durch einen verbindlichen Guard in Dev-Workflow und CI.

## Eingeführte Gates
1. **MIN_SCOPE**: `>= 7` Dateien oder `>= 200` LOC.
2. **MIN_TESTS**: `>= 6` Test-Delta (Test-LOC).
3. **Evidence Required**: dieses Dokument muss in der PR vorhanden sein.
4. **Lane Overlap Check**: Fail bei Dateiüberlappung mit anderen lokalen `codex/*`-Branches.

## CI-Gate
- Command: `bash scripts/dev/pr_quality_guard.sh --ci`
- Workflow: `.github/workflows/ci.yml` (PR-Job `pr-quality-guard`)

## Simulationen
- Thin PR: **FAIL**
- Solid PR: **PASS**
- Overlap PR: **FAIL**

## 2026-03-08 Addendum
- Case: Layout-only hardening (`app/templates/layout.html`) to remove unused font preload warning.
- Initial result: **FAIL** (MIN_SCOPE, MIN_TESTS).
- Normalized result: **PASS target** after adding focused regression tests and evidence docs without widening runtime scope.

## 2026-03-09 Addendum
- Case: Session-tenant enforcement for generic Tool Actions API execution path.
- Security objective: block cross-tenant payload spoofing via `/api/<tool>/actions/<name>`.
- Evidence set:
  - Runtime enforcement in `app/modules/actions_api.py`
  - Integration regression in `tests/integration/test_emailpostfach_ai_actions.py`
  - Additional regression coverage in:
    - `tests/domain/aufgaben/test_actions_api.py`
    - `tests/domain/einstellungen/test_settings_actions_api.py`
  - Policy docs:
    - `docs/security/SESSION_TENANT_ENFORCEMENT_POLICY.md`
    - `docs/security/TOOL_ACTIONS_TENANT_BINDING_POLICY.md`


## 2026-03-09 Addendum (Small PR / Conflict-Prevention Policy)
- Ziel: große gemischte PRs unattraktiv machen und Konfliktrate gegen Shared-Core senken.
- Neue Guard-Policy im Script `scripts/dev/pr_quality_guard.sh`:
  1. `MAX_SCOPE`: nur kleine Diff-Fläche (`<=12` Dateien und `<=350` LOC).
  2. `Focused Scope`: maximal `3` Änderungsbereiche, um fachfremde Nebenänderungen zu bremsen.
  3. `Main-first`: `origin/main` als verpflichtende Basis in CI; lokal Warnung bei fehlendem Remote-Ref.
  4. Shared-Core-Hotspot-Block für konfliktträchtige Kernpfade (separater PR erforderlich).
  5. `MIN_TESTS` und Evidence-Report bleiben Pflicht für nachvollziehbare Test-Evidence.
- Ergebnis: konfliktärmere, reviewbare Einzel-PRs ohne Branch-Stacking-Mechanik.

## 2026-03-10 Addendum (PR #691 Medium/High-Confidence Bandit Gate)
- Scope:
  - `.github/workflows/pipeline.yml` (ursprünglicher Vorschlag)
  - `.github/workflows/ci.yml` (nach CI-Delegation in PR #675 maßgeblich)
  - dieses Evidence-Update
- Ziel: Bandit-Gate blockiert risikoreiche neue Python-Befunde auf geänderten Pfaden (PR-/Push-Delta), statt globaler Altlast-Blockade.
- Sicherheitsnutzen:
  - neue risikoreiche Änderungen werden strikt geblockt,
  - historische Befunde außerhalb des Deltas bleiben separat sanierbar.
- Validierung:
  - Workflow YAML parsebar (`pipeline.yml` + `ci.yml`).
  - Job schreibt die gescannten Ziele (`bandit-targets.txt`) und bricht bei Policy-Verstoß ab.

## 2026-03-10 Addendum (PR #674 Incremental Bandit Gate)
- Scope:
  - `.github/workflows/pipeline.yml`
  - dieses Evidence-Update
- Ziel: Bandit bleibt policy-driven (`severity>=medium`, `confidence>=medium`), aber scannt in PR/Push nur geänderte Python-Ziele (inkrementelles Gate).
- Sicherheitsnutzen:
  - verhindert neue Medium/High-Befunde in geänderten Pfaden,
  - blockiert nicht pauschal auf historische Altbefunde außerhalb des PR-Scopes.
- Validierung:
  - Workflow YAML parsed (`yaml.safe_load`) im CI-Job.
  - Bandit-Targets werden im Job protokolliert (`bandit-targets.txt`) und als Policy-Gate ausgewertet.
