# Core Endpoint Matrix (Canonical Owner)

Stand: Stabilisierung `core endpoint layer`.

## Ziel
Doppelte/konkurrierende Tool-Routen zwischen `app/web.py` und `app/routes/*` wurden auf **einen Canonical Owner** reduziert.

## Canonical Owner je Haupt-Route

| Route | Methoden | Canonical Owner | Hinweis |
|---|---|---|---|
| `/dashboard` | GET | `app/web.py` | Haupt-Dashboard inkl. Navigation |
| `/upload` | GET, POST | `app/web.py` | Upload-Flow + Progress-API in `web` |
| `/review/<token>/kdnr` | GET, POST | `app/web.py` | Wizard-Flow |
| `/done/<token>` | GET | `app/web.py` | Abschlussseite |
| `/projects` | GET | `app/web.py` | Kanban/Project-Hub mit Fallback statt 500 |
| `/tasks` | GET | `app/web.py` | Task-Board mit defensivem Empty-State |
| `/calendar` | GET | `app/web.py` | Kalender-Ansicht |
| `/calendar/export.ics` | GET | `app/web.py` | ICS-Export (neu im `web`-Owner) |
| `/email` | GET | `app/web.py` | E-Mail-Tab |
| `/messenger` | GET | `app/web.py` | Messenger-Tab |
| `/visualizer` | GET | `app/web.py` | Visualizer-Seite |
| `/time` | GET | `app/web.py` | Zeiterfassung |
| `/settings` | GET | `app/web.py` | Settings mit defensivem DB-Fallback |

## API-Routen (Tool-spezifisch)

| Route | Methoden | Canonical Owner | Hinweis |
|---|---|---|---|
| `/api/chat` | POST | `app/web.py` | Primärer Chat-Endpunkt |
| `/api/chat/compact` | GET, POST | `app/web.py` | Compact Chat/Widget |
| `/api/progress` | GET | `app/web.py` | Upload-Fortschritt |
| `/api/progress/<token>` | GET | `app/web.py` | Upload-Fortschritt je Token |
| `/api/visualizer/*` | GET, POST | `app/routes/visualizer.py` | Visualizer-Daten-/Render-API |
| `/api/dashboard/*` | GET, POST | `app/routes/dashboard_api.py` | Dashboard-API namespace |

## Flask `url_map` Prüfhinweis

In einer vollständig installierten Runtime kann die aktive Matrix mit folgendem Snippet verifiziert werden:

```python
from collections import defaultdict
from app import create_app

app = create_app()
rules = defaultdict(list)
for rule in app.url_map.iter_rules():
    key = (rule.rule, tuple(sorted(rule.methods - {"HEAD", "OPTIONS"})))
    rules[key].append(rule.endpoint)

for key, endpoints in sorted(rules.items()):
    if len(endpoints) > 1:
        print("DUPLICATE", key, endpoints)
```

Erwartung nach Fix: **keine konkurrierenden Rules** für die oben genannten Tool-Routen.
