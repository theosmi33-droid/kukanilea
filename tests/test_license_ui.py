from __future__ import annotations

import re
from pathlib import Path

from app import create_app, web


def _login(client, role: str = "ADMIN") -> None:
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = role
        sess["tenant_id"] = "KUKANILEA"


def _csrf_from_html(payload: bytes) -> str:
    match = re.search(rb'name="csrf_token"\s+value="([^"]+)"', payload)
    assert match is not None
    return match.group(1).decode("utf-8")


def test_license_page_forbidden_for_non_admin() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client, role="OPERATOR")

    res = client.get("/license")
    assert res.status_code == 403
    data = res.get_json() or {}
    assert data.get("error", {}).get("code") == "forbidden"


def test_license_page_renders_for_admin() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client, role="ADMIN")

    res = client.get("/license")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Lizenzstatus" in html
    assert "Lizenz aktivieren" in html


def test_license_activation_allowed_while_read_only(
    tmp_path: Path, monkeypatch
) -> None:
    app = create_app()
    app.config.update(
        TESTING=True,
        SECRET_KEY="test",
        READ_ONLY=True,
        LICENSE_REASON="trial_expired",
    )
    app.config["LICENSE_PATH"] = tmp_path / "license.json"
    app.config["TRIAL_PATH"] = tmp_path / "trial.json"
    app.config["LICENSE_CACHE_PATH"] = tmp_path / "license_cache.json"

    client = app.test_client()
    _login(client, role="ADMIN")

    page = client.get("/license")
    assert page.status_code == 200
    csrf = _csrf_from_html(page.data)

    monkeypatch.setattr(web, "load_license", lambda _: {"valid": True, "reason": "ok"})
    monkeypatch.setattr(
        web,
        "load_runtime_license_state",
        lambda **_: {
            "plan": "PRO",
            "trial": False,
            "trial_days_left": 0,
            "expired": False,
            "device_mismatch": False,
            "read_only": False,
            "reason": "ok",
            "grace_active": False,
            "grace_days_left": 0,
            "validated_online": False,
            "last_validated": "",
        },
    )

    res = client.post(
        "/license",
        data={"csrf_token": csrf, "license_json": '{"signature":"dummy"}'},
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert app.config["READ_ONLY"] is False
    assert app.config["PLAN"] == "PRO"
    html = res.get_data(as_text=True)
    assert "Lizenz aktiviert." in html
