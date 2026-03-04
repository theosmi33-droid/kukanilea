# Test Profiles (Smoke / Standard / Full)

## Ziel
Stabile, reproduzierbare Testläufe mit klaren Profilen und ohne unbeabsichtigte externe Abhängigkeiten.

## Profile

### Smoke
Schneller Vertrauenscheck für lokale Iteration.

```bash
./scripts/tests/run_profile.sh smoke
```

### Standard
Default-Profil für lokale Regressionen und CI-sichere Läufe.

```bash
./scripts/tests/run_profile.sh standard
```

### Full
Vollständiger Testlauf inkl. langsamer/exhaustiver Bereiche.

```bash
./scripts/tests/run_profile.sh full
```

## Direkte pytest-Kommandos (optional)

```bash
pytest -m "smoke or (unit and not slow)" -q --maxfail=1
pytest -m "not full and not external" -q
pytest -q
```

## Externe Abhängigkeiten bewusst erlauben
Tests blockieren standardmäßig Netz/Ollama/SMB. Nur explizit mit Marker `external` zulassen.

```bash
pytest -m external -q
```
