from __future__ import annotations

import csv
import io
import json

from app.core.gewerke_profiles import reset_profiles_cache
from app.modules.time import logic as time_logic


def test_time_export_applies_profile_rules_per_tenant(monkeypatch):
    monkeypatch.setenv(
        "KUKANILEA_GEWERK_PROFILES_JSON",
        json.dumps(
            {
                "profiles": {
                    "elektro": {
                        "gewerk_name": "Elektro",
                        "time_export_rules": {
                            "rounding_minutes": 30,
                            "decimal_places": 1,
                            "include_approval_fields": False,
                        },
                    }
                }
            }
        ),
    )
    monkeypatch.setenv("KUKANILEA_TENANT_PROFILE_MAP", json.dumps({"kukanilea": "elektro"}))
    reset_profiles_cache()

    monkeypatch.setattr(
        time_logic,
        "time_entries_list",
        lambda **_: [
            {
                "id": 7,
                "project_id": 2,
                "project_name": "Neuinstallation",
                "user": "admin",
                "start_at": "2026-03-05T08:00:00Z",
                "end_at": "2026-03-05T08:20:00Z",
                "duration_seconds": 1200,
                "note": "Kabelzug",
                "approval_status": "APPROVED",
                "approved_by": "lead",
                "approved_at": "2026-03-05T09:00:00Z",
            }
        ],
    )

    data = time_logic.time_entries_export_csv(tenant_id="KUKANILEA", limit=10)
    rows = list(csv.DictReader(io.StringIO(data)))

    assert rows
    assert "approval_status" not in rows[0]
    assert rows[0]["duration_seconds"] == "1800"
    assert rows[0]["duration_hours"] == "0.5"
    reset_profiles_cache()
