# Bootstrap & Doctor

Dieses Dokument definiert den reproduzierbaren Local-Setup-Flow für KUKANILEA.

## Ziel
- Entwicklerumgebung in <10 Minuten bootstrapbar.
- Lokale Checks entsprechen dem CI-Smoke-Corridor.

## One-command Bootstrap

```bash
make bootstrap
```

Was passiert:
1. `scripts/bootstrap.sh` prüft die aktive `python3` Version gegen `.python-version`.
2. `.build_venv` wird erstellt (oder wiederverwendet).
3. `requirements.txt` und `requirements-dev.txt` werden installiert.
4. Playwright Browser werden installiert (außer `BOOTSTRAP_SKIP_PLAYWRIGHT=1`).
5. `pre-commit` Hooks werden installiert.

## Diagnose

```bash
make doctor
```

`scripts/doctor.sh` liefert klare PASS/FAIL-Ausgaben für:
- `python3`
- `pip`
- `sqlite3`
- `rg`
- `gh`
- `playwright`
- `.build_venv`

Bei FAIL:
- `make bootstrap` erneut ausführen.
- Sicherstellen, dass die in `.python-version` festgelegte Python-Version aktiv ist.

## CI-Parität

Lokale Smoke-Checks:

```bash
make test-smoke
./scripts/ops/healthcheck.sh --ci
```

CI nutzt denselben Bootstrap-Weg und trennt bewusst zwischen:
- schnellem Smoke-Corridor (`lint + unit-smoke + healthcheck`)
- vollem Validierungsjob
