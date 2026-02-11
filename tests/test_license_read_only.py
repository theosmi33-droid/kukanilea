from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from app import create_app
from app.license import load_runtime_license_state


def test_read_only_blocks_mutating_requests() -> None:
    app = create_app()
    app.config["READ_ONLY"] = True
    app.config["LICENSE_REASON"] = "trial_expired"
    client = app.test_client()

    resp = client.post("/api/chat", json={"q": "hallo"})
    assert resp.status_code == 403
    payload = resp.get_json() or {}
    assert payload.get("error", {}).get("code") == "read_only"


def test_trial_logic_marks_expired_and_creates_state(tmp_path: Path) -> None:
    trial_path = tmp_path / "trial.json"
    trial_path.write_text(
        json.dumps({"start": (date.today() - timedelta(days=30)).isoformat()}),
        encoding="utf-8",
    )

    state = load_runtime_license_state(
        license_path=tmp_path / "missing_license.json",
        trial_path=trial_path,
        trial_days=14,
    )
    assert state["trial"] is True
    assert state["expired"] is True
    assert state["read_only"] is True

    fresh_trial_path = tmp_path / "fresh_trial.json"
    fresh_state = load_runtime_license_state(
        license_path=tmp_path / "missing_license.json",
        trial_path=fresh_trial_path,
        trial_days=14,
    )
    assert fresh_state["trial"] is True
    assert fresh_state["read_only"] is False
    assert fresh_trial_path.exists()
