from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import create_app


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _login_session(client, *, role: str = "ADMIN") -> None:
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = role
        sess["tenant_id"] = "KUKANILEA"


def test_idle_timeout_default_60_logout() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login_session(client, role="ADMIN")

    now = datetime.now(timezone.utc)
    with client.session_transaction() as sess:
        sess["session_created_at"] = _iso_utc(now - timedelta(minutes=10))
        sess["last_activity"] = _iso_utc(now - timedelta(minutes=61))
        sess["idle_timeout_minutes"] = 60

    res = client.get("/settings", follow_redirects=False)
    assert res.status_code in (302, 303)
    assert "/login" in str(res.headers.get("Location") or "")


def test_idle_timeout_bounds_enforced() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login_session(client, role="ADMIN")

    with client.session_transaction() as sess:
        sess["csrf_token"] = "csrf-test"

    low = client.post(
        "/settings/idle-timeout",
        data={"idle_timeout": "5", "csrf_token": "csrf-test"},
        follow_redirects=False,
    )
    assert low.status_code in (302, 303)
    with client.session_transaction() as sess:
        assert sess["idle_timeout_minutes"] == 15

    high = client.post(
        "/settings/idle-timeout",
        data={"idle_timeout": "1000", "csrf_token": "csrf-test"},
        follow_redirects=False,
    )
    assert high.status_code in (302, 303)
    with client.session_transaction() as sess:
        assert sess["idle_timeout_minutes"] == 480


def test_absolute_timeout_8h_logout() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login_session(client, role="ADMIN")

    now = datetime.now(timezone.utc)
    with client.session_transaction() as sess:
        sess["session_created_at"] = _iso_utc(now - timedelta(hours=9))
        sess["last_activity"] = _iso_utc(now - timedelta(minutes=1))
        sess["idle_timeout_minutes"] = 480

    res = client.get("/settings", follow_redirects=False)
    assert res.status_code in (302, 303)
    assert "/login" in str(res.headers.get("Location") or "")


def test_whitelist_login_does_not_timeout() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()

    res = client.get("/login", follow_redirects=False)
    assert res.status_code in (200, 302, 303)
