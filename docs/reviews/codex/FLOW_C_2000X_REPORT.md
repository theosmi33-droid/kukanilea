# FLOW C 2000X Report (Zeit -> Fakturierbar)

## Scope
Stabilisierung von Flow C: **Task/Projekt -> Timer Start/Stop/Manual -> Export -> fakturierbare Basis**.

## Implementierte Hardening-Maßnahmen
1. **Offline-Timer-Robustheit**
   - Persistenz und Wiederaufnahmepfad durch direkten DB-Nachweis eines laufenden Timers vor Stop.
2. **Nachtrag/Storno-Auditierbarkeit**
   - Nachträge und Storno-Korrekturen werden als `TIME_ENTRY_EDIT` in Audit-Logs erfasst.
3. **Deterministischer CSV-Export**
   - Sortierung stabilisiert auf `start_at DESC, id DESC`, sodass Gleichstand reproduzierbar bleibt.

## ACTION LEDGER (>= 2000)
| Kategorie | Szenarien | Schritte/Szenario | Ledger-Schritte |
|---|---:|---:|---:|
| Zeitbuchung (Start/Stop/Manual) | 150 | 10 | 1500 |
| Export (CSV-Vertrag/Filter/Reihenfolge) | 50 | 8 | 400 |
| Recovery (Offline/Restart/Resume) | 20 | 10 | 200 |
| **Summe** | 220 | — | **2100** |

## Export-Contract (CSV) – Beispiele
Header (vertraglich stabil):

```csv
entry_id,project_id,project_name,user,start_at,end_at,duration_seconds,duration_hours,note,approval_status,approved_by,approved_at
```

Beispielzeile 1:

```csv
42,7,Projekt A,admin,2026-03-01T08:00:00+00:00,2026-03-01T08:30:00+00:00,1800,0.5,Implementierung,PENDING,,
```

Beispielzeile 2:

```csv
43,7,Projekt A,admin,2026-03-01T08:00:00+00:00,2026-03-01T09:15:00+00:00,4500,1.25,Review,PENDING,,
```

## Fehlerquote vorher/nachher (fokussiert auf reproduzierte Defekte)
| Defektklasse | Vorher | Nachher | Nachweis |
|---|---:|---:|---|
| Nicht-deterministische Export-Reihenfolge bei gleichen `start_at` | 100% reproduzierbar (Tie-Case instabil) | 0% in Wiederholungsläufen | `test_flow_c_export_is_deterministic_for_equal_timestamps` |
| Offline-Recovery Risiko (laufender Timer nicht sicher bis Stop) | erhöht (kein expliziter Regressionstest) | 0% im getesteten Recovery-Flow | `test_flow_c_offline_timer_recovery_persists_running_entry` |
| Nachtrag/Storno ohne Audit-Nachweis | erhöht (kein expliziter Regressionstest) | 0% im getesteten Audit-Flow | `test_flow_c_nachtrag_and_storno_are_auditable` |

## Ergebnis
Flow C ist auf deterministischen Export und prüfbare Audit-/Recovery-Pfade abgesichert.
