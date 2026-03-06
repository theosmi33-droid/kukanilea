# Tool Interface Extension: Actions API Contract

Version: `2026-03-06`  
Status: Draft (for implementation alignment)

Dieses Dokument erweitert das bestehende ToolInterface (`summary`/`health`) um ein standardisiertes Actions-Contract.

## 1) Endpoints

### 1.1 `GET /api/<tool>/actions`
Liefert die verfügbaren Actions inkl. Input/Output-Schema, Permission-Anforderungen und Confirm-Gate-Strategie.

**Response (200)**

```json
{
  "tool": "projects",
  "contract_version": "2026-03-06",
  "actions": [
    {
      "name": "create_project",
      "title": "Projekt anlegen",
      "description": "Legt ein neues Projekt an.",
      "input_schema": {"$ref": "#/components/schemas/CreateProjectInput"},
      "output_schema": {"$ref": "#/components/schemas/CreateProjectOutput"},
      "permissions": {
        "resource": "projects",
        "operation": "write",
        "roles_any": ["admin", "manager"]
      },
      "confirm_gate": {
        "mode": "required",
        "ttl_seconds": 600
      },
      "idempotent": true
    }
  ]
}
```

### 1.2 `POST /api/<tool>/actions/<name>`
Führt eine Action aus (direkt oder via Confirm-Gate-Flow).

**Headers**
- `Content-Type: application/json`
- `Idempotency-Key: <opaque-string>` (required für mutierende Actions)

**Request Body**

```json
{
  "payload": {},
  "confirm": {
    "mode": "propose|confirm",
    "token": "optional-on-confirm"
  },
  "context": {
    "request_id": "req_123",
    "tenant_id": "tenant_a"
  }
}
```

**Response Varianten**

- `200 OK`: Action ausgeführt.
- `202 Accepted`: Confirm erforderlich, Proposal zurückgegeben.
- `403 Forbidden`: fehlende Rolle/Berechtigung.
- `409 Conflict`: Idempotency-Konflikt (gleicher Key, anderer Payload-Hash).
- `422 Unprocessable Entity`: Schema-Validierung fehlgeschlagen.

## 2) Permissions Model (Role-Based)

Jede Action MUSS ein deklaratives Policy-Objekt definieren:

- `resource`: Domänenressource (z. B. `projects`, `invoice`, `tenant.users`)
- `operation`: `read|write|delete|execute|admin`
- `roles_any`: mindestens eine dieser Rollen erlaubt
- `roles_all` (optional): alle Rollen müssen vorhanden sein
- `conditions` (optional): kontextabhängige Checks (tenant match, ownership etc.)

Autorisierung wird vor Confirm-Gate und vor Ausführung evaluiert.

## 3) Confirm-Gate Protocol (Two-Step)

Für sensitive/mutierende Actions (`confirm_gate.mode=required`) gilt:

1. **Propose** (`confirm.mode=propose`, ohne Token)
   - Server validiert Schema + Berechtigungen.
   - Server gibt `202` + Proposal zurück:
     - `confirm.token` (kurzlebig, signiert)
     - `confirm.expires_at`
     - `preview` (human-readable Zusammenfassung)
     - `audit.event_id`

2. **Confirm** (`confirm.mode=confirm` + Token)
   - Server prüft Token, TTL, Rollen-Kontext, Idempotency-Key.
   - Bei Erfolg wird Action atomar ausgeführt und `200` geliefert.

### Sicherheitsregeln
- Confirm-Token MUSS an `actor_id`, `tenant_id`, `tool`, `action_name`, `payload_hash` gebunden sein.
- Token ist One-Time-Use.
- Proposal und Execute erzeugen jeweils Audit-Events.

## 4) Audit Event Schema

Jeder Actions-Aufruf MUSS strukturierte Audit-Events schreiben:

- `action.proposed`
- `action.confirmed`
- `action.executed`
- `action.denied`
- `action.idempotency_replay`

Pflichtfelder:
- `event_id`, `timestamp`, `event_type`
- `tool`, `action_name`, `tenant_id`, `actor_id`
- `request_id`, `idempotency_key`
- `decision` (`allow|deny|replay|error`)
- `payload_hash`
- `result_ref` (optional technische Referenz auf Ergebnis)

## 5) Idempotency Keys

Für mutierende Actions ist `Idempotency-Key` Pflicht.

Semantik:
- Gleiches `(tenant_id, tool, action_name, actor_id, idempotency_key)` und gleicher `payload_hash` ⇒ Server liefert gespeichertes Ergebnis (`replay`).
- Gleiches Key aber anderer `payload_hash` ⇒ `409 conflict`.
- TTL für gespeicherte Keys: mindestens 24h (empfohlen 72h).

## 6) Normative Validation Rules

- Action `name` MUST match `^[a-z][a-z0-9_]{2,63}$`.
- `input_schema` und `output_schema` MUST be valid JSON Schema Draft 2020-12.
- `permissions.roles_any` MUST NOT be empty.
- Mutierende Actions MUST declare `idempotent=true` und Idempotency-Key enforcement.
- `confirm_gate.mode=required` MUST be set for `write|delete|admin` unless explicitly whitelisted as safe-idempotent by policy.

## 7) Minimal Execution Contract (Response Envelope)

```json
{
  "ok": true,
  "tool": "projects",
  "action": "create_project",
  "status": "executed|proposed|replayed|denied",
  "result": {},
  "confirm": {
    "required": false,
    "token": null,
    "expires_at": null
  },
  "audit": {
    "event_id": "evt_..."
  }
}
```

## 8) Backward Compatibility

- Bestehende ToolInterface Endpoints (`/summary`, `/health`) bleiben unverändert.
- Neues Actions-Interface ist additive Erweiterung.
- Clients dürfen capability-detect via `GET /api/<tool>/actions` (404 => kein Actions-Support).
