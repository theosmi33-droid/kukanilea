from __future__ import annotations

import pytest

from app.tools.action_registry import action_registry
from app.tools.registry import registry
from tests.stubs.authdb_stub import _AuthDBStub
from tests.time_utils import utc_now_iso


@pytest.fixture(autouse=True)
def patch_auth_db(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    """Patch AuthDB only for integration-contract stability tests."""
    nodeid = request.node.nodeid
    if "integration_contract_stability" not in nodeid:
        return

    monkeypatch.setattr("app.db.AuthDB", _AuthDBStub, raising=False)
    monkeypatch.setattr("app.web.AuthDB", _AuthDBStub, raising=False)


@pytest.fixture(autouse=True)
def isolate_external_dependencies(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    """Disable live external systems unless a test opts in via @pytest.mark.external."""
    if request.node.get_closest_marker("external"):
        return

    monkeypatch.setenv("OLLAMA_ENABLED", "0")
    monkeypatch.setenv("KUKANILEA_SMB_REACHABLE", "0")
    monkeypatch.setenv("KUKANILEA_ALLOW_NETWORK", "0")

    def _blocked_request(*_args, **_kwargs):
        raise RuntimeError("External HTTP access disabled in tests. Use @pytest.mark.external to opt in.")

    try:
        import requests  # noqa: F401
    except ModuleNotFoundError:
        return

    monkeypatch.setattr("requests.sessions.Session.request", _blocked_request, raising=True)


@pytest.fixture()
def seeded_auth_db(app):
    """Seed default tenant/admin into the active app auth db."""
    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        from app.auth import hash_password

        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("admin", hash_password("admin"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)
        return auth_db


@pytest.fixture(autouse=True)
def isolate_registry_and_action_state(request: pytest.FixtureRequest):
    """Keep global tool/action registries isolated for action/registry-centric tests."""
    nodeid = request.node.nodeid
    needs_isolation = (
        "test_action_" in nodeid
        or "test_registry_" in nodeid
        or nodeid.startswith("tests/agents/test_action_registry.py")
        or nodeid.startswith("tests/core/test_mia_audit_layer.py")
    )
    if not needs_isolation:
        yield
        return

    previous_tools = dict(registry.tools)
    previous_actions = action_registry.snapshot()
    try:
        yield
    finally:
        registry.tools.clear()
        registry.tools.update(previous_tools)
        action_registry.reset(previous_actions)
