# Developer Bootstrap Flow (<10 Minuten)

Ziel: `clone -> bootstrap -> smoke tests` mit einem Time-to-green unter 10 Minuten.

## Ablauf

```bash
git clone <repo-url>
cd kukanilea
bash scripts/dev_bootstrap.sh
```

Der Bootstrap-Run erledigt automatisch:
1. `.venv` erstellen (falls nicht vorhanden)
2. Python-Abhängigkeiten installieren
3. Dev-User seeden (`scripts/seed_dev_users.py`)
4. Demo-Daten seeden (`scripts/seed_demo_data.py`)
5. Smoke-Test ausführen (`python -m app.smoke`)

## App starten

```bash
source .venv/bin/activate
python run.py server --host 127.0.0.1 --port 5051
```

## Verifikation

```bash
pytest -q
python scripts/seed_demo_data.py
```

## Known issues / Fallback

- Wenn DB-Schreiben blockiert ist (read-only FS/DB-Lock), kann `seed_demo_data.py` fehlschlagen.
- Fallback:
  1. Read-only Fixtures verwenden (Smoke weiterhin ausführbar).
  2. Demo-Daten via manuellem SQL-Import in eine beschreibbare SQLite-Datei einspielen.
  3. Danach `KUKANILEA_AUTH_DB` auf diese Datei zeigen lassen und Seed erneut starten.
