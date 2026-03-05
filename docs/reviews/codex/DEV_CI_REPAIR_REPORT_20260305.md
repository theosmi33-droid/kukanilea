# DEV CI Repair Report — Playwright Doctor False Negative (PR #315)

## Auftrag
Lane `dev-ci`: Bootstrap/Doctor so korrigieren, dass CI nur bei **tatsächlich blockierter Playwright-Ausführung** failt.

## 1) Reproduktion des Fehlers (vor Fix)
Repro mit altem `scripts/dev/doctor.sh` (aus `HEAD~1`) und einer Python-Stub-Umgebung, in der gilt:
- `import playwright` funktioniert
- `python -m playwright --version` funktioniert
- Node-CLI `playwright` fehlt im `PATH`

Kommando:

```bash
PATH="/usr/bin:/bin" PYTHON="$fake_py" bash "$old_src" --strict
```

Ergebnis vor Fix:

```text
[doctor] OK: python module 'playwright' available
[doctor] WARN: playwright CLI missing (use: /tmp/tmp.R8F76qLSQL -m playwright install --with-deps chromium)
[doctor] FAIL: 1 missing/invalid checks.
old_exit:4
```

Damit ist die False-Negative reproduziert: erforderliche Python-Ausführung war möglich, trotzdem FAIL wegen optionaler Node-CLI.

## 2) Korrekturstrategie
`doctor.sh` trennt jetzt sauber in vier Ebenen:
1. Python-Modul `playwright` importierbar (required)
2. Python-CLI `python -m playwright` funktionsfähig (required)
3. Node-CLI `playwright` im PATH (optional)
4. Chromium-Binary verfügbar (`--ci`: required, lokal: warning)

Zusätzlich:
- Modusumschaltung über `--ci` und `CI`-Env.
- Präzise Recovery-Hinweise pro FAIL/WARN.
- Keine irreführende FAIL-Meldung mehr für fehlende Node-CLI.

## 3) Verifikation nach Fix
Mit derselben Stub-Umgebung:

```bash
PATH="/usr/bin:/bin" PYTHON="$fake_py" bash scripts/dev/doctor.sh --strict
```

Ergebnis nach Fix:

```text
[doctor] OK: Playwright Python CLI available via '/tmp/tmp.R8F76qLSQL -m playwright' (Version 1.52.0)
[doctor] OK: Playwright chromium browser binary present
[doctor] WARN: Node Playwright CLI missing (optional). Preferred path is '/tmp/tmp.R8F76qLSQL -m playwright'.
[doctor] All checks passed
new_exit:0
```

## 4) Testabdeckung (neu)
Neue Tests decken ab:
- doctor local mode
- doctor CI mode
- missing module
- missing browser binaries
- fallback/skip branch bei fehlendem Modul
- Node-CLI optional (present/missing)
- non-strict warning summary

Datei: `tests/ops/test_doctor_playwright_checks.py` (8 Tests).

## 5) Hard-Gates
- **MIN_SCOPE**: erfüllt (umfangreicher Test+Script+Doc-Fix)
- **MIN_TESTS**: erfüllt (>=7, konkret 8 neue Tests)
- **CI_GATE**: `pytest -q tests --ignore=tests/e2e` bestanden
