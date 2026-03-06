# Tool Contracts – Actions API Erweiterung (Gemini Prompt 4)

Status: Draft v0.1  
Basis: bestehende ToolInterface-Contracts (`/api/<tool>/summary`, `/api/<tool>/health`)

## 1) Ziel

Erweiterung des bestehenden ToolInterface um ein standardisiertes **Actions API Contract** für alle Contract-Tools:

- `GET /api/<tool>/actions` → verfügbare Actions + Input/Output-Schema-Metadaten
- `POST /api/<tool>/actions/<name>` → Action ausführen (inkl. Confirm-Gate, Permissions, Idempotenz)

Die Erweiterung ist **additiv** und bleibt rückwärtskompatibel zu bestehenden Summary-/Health-Endpunkten.

---

## 2) Endpunkte

## 2.1 `GET /api/<tool>/actions`

Liefert die Action-Liste eines Tools sowie Schemainformationen.

**Response (200):**

- `tool`: Tool-Name
- `version`: Contract-Version (z. B. `2026-03-06`)
- `actions[]`: deklarative Beschreibung jeder Action
  - `name`: stabiler Name (URI-safe)
  - `description`: kurze Beschreibung
  - `input_schema`: JSON Schema (Draft 2020-12)
  - `output_schema`: JSON Schema (Draft 2020-12)
  - `required_role`: minimale Rolle
  - `confirm_gate`: ob zweistufige Bestätigung verpflichtend ist
  - `idempotent`: ob Action idempotent erwartet ist
  - `idempotency_ttl_seconds`: dedupe-Fenster

**Fehlerfälle:**

- `404` Tool unbekannt
- `503` Tool backend nicht bereit (optional: `status=degraded` analog Contract-Logik)

## 2.2 `POST /api/<tool>/actions/<name>`

Führt eine Action aus oder startet den Confirm-Gate-Flow.

**Request-Felder:**

- `input`: action-spezifische Payload
- `confirm`: Confirm-Token (optional in `propose`, Pflicht in `confirm`)
- `confirm_token`: vom Server signiertes Token aus Propose-Phase
- `phase`: `propose` | `confirm`
- `idempotency_key`: Client-Idempotenzschlüssel (empfohlen/pflicht je Action)
- `request_id`: optionaler Client-Correlation-Key
- `meta`: optionaler Kontext (z. B. UX channel)

**Response-Modi:**

1. **Propose-Mode (`phase=propose`)**  
   Server validiert Input + Permission, führt Action noch nicht aus und liefert:
   - `state=confirm_required`
   - `confirm_token` (kurzlebig, signiert)
   - `preview` (sanitized Auswirkung)
   - `expires_at`

2. **Confirm-Mode (`phase=confirm`)**  
   Server validiert Confirm-Token + confirm-Wert + Permission + Idempotenz und führt Action aus:
   - `state=executed`
   - `result` (schema-konform)
   - `audit_ref` (Audit Event ID)

3. **Idempotent Replay**
   - `state=idempotent_replay`
   - `result` aus vorherigem erfolgreichen Lauf

**Fehlerfälle:**

- `400` Validation Error (`input`, `phase`, `confirm`)
- `401` Auth fehlt/ungültig
- `403` Rolle nicht ausreichend
- `404` Tool/Action unbekannt
- `409` Idempotency-Konflikt (gleicher Key, anderer Payload-Hash)
- `410` Confirm-Token abgelaufen
- `422` Confirm erforderlich, aber nicht erfüllt

---

## 3) Permissions Model (Role-Based)

Minimalmodell:

- `viewer`: read-only, keine writes
- `operator`: standard write Actions
- `admin`: sensitive/destructive Actions
- `owner` (optional tenant-spezifisch): administrative Superset-Rolle

Regeln:

1. Jede Action deklariert `required_role`.
2. Evaluierung über serverseitigen `role_resolver(user, tenant, tool)`.
3. Rolle wird bei **propose und confirm** geprüft (TOCTOU-Härtung).
4. Rolle + Decision werden auditierbar geloggt.

Optional erweiterbar durch:

- `allowed_roles[]` statt Single-MinRole
- Policy Attributes (tenant tier, feature flag, time window)

---

## 4) Confirm-Gate Protokoll (Two-Step)

## 4.1 Ziel

Risikobehaftete Writes nur zweistufig:

`propose -> confirm -> execute`

## 4.2 Ablauf

1. Client sendet `phase=propose`.
2. Server prüft Input/Permission und erzeugt `confirm_token` mit:
   - `tool`, `action`, `tenant`, `subject`, `input_hash`, `expires_at`, `nonce`.
3. Client zeigt Preview + Risikotext.
4. Client sendet `phase=confirm` + `confirm=true` + `confirm_token`.
5. Server validiert Token + Hash + Expiry + Permission erneut und führt aus.

## 4.3 Sicherheitsregeln

- Confirm-Token muss signiert (HMAC/EdDSA) und kurzlebig sein.
- Input-Bindung via `input_hash` zwingend.
- Replay-Schutz über `nonce` + idempotency store.
- Bei Role-Change zwischen propose/confirm: `403`.

---

## 5) Audit Event Schema

Jeder Actions-Call erzeugt mindestens ein Audit Event:

- `action.proposed`
- `action.confirmed`
- `action.executed`
- `action.denied`
- `action.replayed`
- `action.failed`

Pflichtfelder:

- `event_id`, `event_type`, `timestamp`
- `tool`, `action`, `tenant_id`
- `actor` (user/service)
- `phase`
- `decision` (`allow`/`deny`)
- `required_role`, `effective_role`
- `idempotency_key`, `idempotency_status`
- `confirm_gate` Objekt (required, token_id, confirmed)
- `request_hash`, `result_hash` (optional bei Fehlern)
- `http_status`, `error_code` (optional)

Audit Events sind append-only und unveränderlich.

---

## 6) Idempotency Keys

## 6.1 Header/Body

Empfehlung:

- Primär: Header `Idempotency-Key`
- Fallback: Body `idempotency_key`

Wenn beide gesetzt: Header gewinnt.

## 6.2 Server-Regeln

1. Scope: `tenant + tool + action + idempotency_key`
2. Store enthält `request_hash`, `status`, `response`, `expires_at`
3. Gleiches Key + gleicher Hash → gespeicherte Antwort replayen
4. Gleiches Key + anderer Hash → `409 idempotency_conflict`
5. TTL konfigurierbar (Default 24h, Action-overridable)

## 6.3 Confirm-Gate Interaktion

- Empfohlen: gleicher Idempotency-Key für propose + confirm Pfad.
- Execution wird nur einmal persistiert; spätere confirms werden replayed.

---

## 7) Kompatibilität mit bestehendem ToolInterface

- Summary/Health bleiben unverändert.
- `details.contract` kann optional um `actions_api: true` erweitert werden.
- Tool ohne Actions-Support liefert:
  - `GET /actions` → `200` mit `actions: []` oder `501 not_implemented`
  - `POST /actions/<name>` → `404 action_not_found`

---

## 8) Referenz-Schemas

Siehe JSON Schema Drafts in `docs/contracts/actions_api/schemas/`:

1. `tool_actions_list.response.schema.json`
2. `tool_action_execute.request.schema.json`
3. `tool_action_execute.response.schema.json`
4. `tool_action_audit_event.schema.json`
5. `tool_action_confirm_token_claims.schema.json`

