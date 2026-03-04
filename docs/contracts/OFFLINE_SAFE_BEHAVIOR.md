# Offline-safe Verhalten (Dashboard Aggregator)

Der Dashboard-Aggregator `GET /api/dashboard/tool-matrix` arbeitet nur mit Summary-Verträgen und behandelt degradierte Backends als darstellbare Zustände.

## Regeln

1. Keine hard-fail Kaskade bei Einzeltool-Fehlern.
2. Jeder Tool-Zustand wird als Kachel gerendert (`ok`, `degraded`, `error`).
3. `degraded_reason` wird sichtbar ausgegeben.
4. Bei kompletter Netzwerkstörung zeigt die UI `offline/degraded` statt leerer/abstürzender Oberfläche.

## UX-Fallback

- Dashboard bleibt navigierbar.
- Upload/Tasks/etc. werden nicht blockiert.
- Status-Aktualisierung ist best effort.
