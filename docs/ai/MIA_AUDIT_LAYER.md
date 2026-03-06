# MIA Audit Layer (kanonisch + launch-evidence-fähig)

## Event-Matrix (kanonisch)

| Event-Typ | Wann | Status | Risiko (typisch) |
|---|---|---|---|
| `mia.intent.detected` | Intent wurde aus Input erkannt | `detected` | `low`/`high` |
| `mia.action.selected` | Route/Action wurde selektiert | `selected` | `low`/`high` |
| `mia.confirm.requested` | Confirm-Gate ausgelöst | `requested` | `medium`/`high` |
| `mia.confirm.granted` | Confirm positiv | `granted` | `medium`/`high` |
| `mia.confirm.denied` | Confirm negativ | `denied` | `medium`/`high` |
| `mia.confirm.expired` | Confirm timeout/invalidiert | `expired` | `medium` |
| `mia.route.blocked` | Route bewusst blockiert | `blocked` | `medium`/`high` |
| `mia.route.executed` | Route erfolgreich ausgeführt | `executed` | `low`/`medium` |
| `mia.external_call.blocked` | Externer Call policybedingt blockiert | `blocked` | `high` |
| `mia.parameter_validation.failed` | Parameter ungültig | `failed` | `low`/`medium` |
| `mia.execution.started` | bestehender Execution-Start | `started` | `medium` |
| `mia.execution.finished` | bestehende Execution-Ende | `finished` | `medium` |
| `mia.execution.failed` | bestehender Execution-Fehler | `failed` | `high` |
| `mia.audit_trail.linked` | Verknüpfung mit audit/eventlog | `finished` | `low` |

## Standard-Payload

Jedes Event nutzt den kanonischen Kern:

```json
{
  "tenant_id": "KUKANILEA",
  "user_id": "alice",
  "action": "core.read_action",
  "status": "selected",
  "risk": "low",
  "meta": {}
}
```

Hinweise:
- Secret-haltige Keys (`token`, `authorization`, `api_key`, …) werden redacted.
- `status` und `risk` sind allowlist-basiert, um Drift in Launch-Evidence zu verhindern.

## Gate-7-Verifikation

Gate 7 kann mit MIA-Audit reproduzierbar verifiziert werden über:
1. Intent+Action-Nachweis (`mia.intent.detected`, `mia.action.selected`)
2. Confirm-Nachweis (`mia.confirm.requested` + granted/denied/expired)
3. Blockierungs-Nachweis (`mia.route.blocked`, `mia.external_call.blocked`)
4. Ausführungs-Nachweis (`mia.route.executed`, `mia.execution.*`)
5. Payload-Pflichtfelder (`tenant_id`, `user_id`, `action`, `status`, `risk`)

Empfohlene SQL-Samples:

```sql
SELECT event_type, COUNT(*)
FROM events
WHERE event_type LIKE 'mia.%'
GROUP BY event_type
ORDER BY event_type;
```

```sql
SELECT id, event_type, payload_json
FROM events
WHERE event_type IN ('mia.intent.detected','mia.action.selected','mia.route.blocked','mia.route.executed')
ORDER BY id DESC
LIMIT 20;
```

## Launch-Evidence-Nutzen

Diese Audit-Schicht liefert:
- deterministische Timeline pro Tenant/User/Action,
- klare Entscheidungsgründe in `meta`,
- redacted Payloads ohne Secret-Leaks,
- stabile Event-Namen für Gate-Reports und Parser.
