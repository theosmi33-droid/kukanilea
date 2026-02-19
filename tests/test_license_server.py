from __future__ import annotations

from license_server.app import create_app


def _payload(customer_id: str) -> dict:
    return {
        "license": {
            "customer_id": customer_id,
            "plan": "PRO",
            "expiry": "2027-12-31",
            "signature": "dummy",
        },
        "device_fingerprint": "fp-001",
        "app": "kukanilea",
    }


def test_validate_active_license(tmp_path) -> None:
    app = create_app(
        {
            "TESTING": True,
            "DB_PATH": tmp_path / "license_active.db",
            "API_TOKEN": "token",
        }
    )
    client = app.test_client()

    upsert = client.post(
        "/api/v1/licenses/upsert",
        json={
            "customer_id": "cust-1",
            "tier": "pro",
            "valid_until": "2027-12-31",
            "status": "active",
        },
        headers={"X-API-Token": "token"},
    )
    assert upsert.status_code == 200

    res = client.post("/api/v1/validate", json=_payload("cust-1"))
    data = res.get_json() or {}
    assert res.status_code == 200
    assert data.get("valid") is True
    assert data.get("tier") == "pro"


def test_validate_revoked_license(tmp_path) -> None:
    app = create_app(
        {
            "TESTING": True,
            "DB_PATH": tmp_path / "license_revoked.db",
            "API_TOKEN": "token",
        }
    )
    client = app.test_client()

    upsert = client.post(
        "/api/v1/licenses/upsert",
        json={
            "customer_id": "cust-2",
            "tier": "pro",
            "valid_until": "2027-12-31",
            "status": "revoked",
        },
        headers={"X-API-Token": "token"},
    )
    assert upsert.status_code == 200

    res = client.post("/api/v1/validate", json=_payload("cust-2"))
    data = res.get_json() or {}
    assert res.status_code == 200
    assert data.get("valid") is False
    assert data.get("reason") == "revoked"


def test_admin_upsert_requires_token_when_configured(tmp_path) -> None:
    app = create_app(
        {
            "TESTING": True,
            "DB_PATH": tmp_path / "license_auth.db",
            "API_TOKEN": "token",
        }
    )
    client = app.test_client()

    res = client.post(
        "/api/v1/licenses/upsert",
        json={
            "customer_id": "cust-3",
            "tier": "pro",
            "valid_until": "2027-12-31",
            "status": "active",
        },
    )
    assert res.status_code == 403
