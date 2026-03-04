from __future__ import annotations

import pytest

from tests.stubs.authdb_stub import _AuthDBStub


@pytest.fixture(autouse=True)
def patch_auth_db(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    """Patch AuthDB only for integration-contract stability tests."""
    nodeid = request.node.nodeid
    if "integration_contract_stability" not in nodeid:
        return

    monkeypatch.setattr("app.db.AuthDB", _AuthDBStub, raising=False)
    monkeypatch.setattr("app.web.AuthDB", _AuthDBStub, raising=False)
