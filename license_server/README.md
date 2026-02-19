# KUKANILEA License Server (Prototype)

Stand: 2026-02-19

This is a minimal production-oriented prototype for online license validation.
It is intentionally simple and designed to match the client contract used in `app/license.py`.

## Goals

- Validate licenses for KUKANILEA runtime (`/api/v1/validate`)
- Support revocation and expiry
- Keep tenant data local in the main app; only license metadata is handled here

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m license_server.app
```

Default server URL: `http://127.0.0.1:5061`

## Configuration

- `LICENSE_SERVER_DB` (default: `license_server/license_server.db`)
- `LICENSE_SERVER_PORT` (default: `5061`)
- `LICENSE_SERVER_API_TOKEN` (optional; required for admin upsert endpoint if set)

## API

### `GET /health`
Returns service health.

### `POST /api/v1/validate`
Request (shape used by app runtime):

```json
{
  "license": {
    "customer_id": "cust-001",
    "plan": "PRO",
    "expiry": "2027-12-31",
    "signature": "..."
  },
  "device_fingerprint": "sha256...",
  "app": "kukanilea"
}
```

Response:

```json
{
  "valid": true,
  "reason": "ok",
  "tier": "pro",
  "valid_until": "2027-12-31"
}
```

### `POST /api/v1/licenses/upsert`
Admin endpoint to create/update license records.
If `LICENSE_SERVER_API_TOKEN` is set, provide header `X-API-Token`.

Minimal request:

```json
{
  "customer_id": "cust-001",
  "tier": "pro",
  "valid_until": "2027-12-31",
  "status": "active"
}
```

## Integration with KUKANILEA app

Set one of:

- `KUKANILEA_LICENSE_VALIDATE_URL=http://127.0.0.1:5061/api/v1/validate`
- or `LICENSE_SERVER_URL=http://127.0.0.1:5061/api/v1/validate`

The app stays offline-first and uses grace handling if the server is unavailable.
