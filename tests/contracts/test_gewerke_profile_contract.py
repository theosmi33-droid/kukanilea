from __future__ import annotations

import json

from app.core.gewerke_profiles import reset_profiles_cache


def test_health_profile_includes_gewerke_profile_configuration(auth_client, monkeypatch):
    monkeypatch.setenv(
        "KUKANILEA_GEWERK_PROFILES_JSON",
        json.dumps(
            {
                "profiles": {
                    "sanitaer": {
                        "gewerk_name": "Sanitär",
                        "document_types": ["RECHNUNG", "WARTUNG"],
                        "required_fields": ["tenant", "kdnr", "doctype"],
                        "task_templates": ["Wartungstermin koordinieren"],
                        "time_export_rules": {"rounding_minutes": 10, "decimal_places": 2},
                    }
                }
            }
        ),
    )
    monkeypatch.setenv("KUKANILEA_GEWERK_PROFILE_ID", "sanitaer")
    reset_profiles_cache()

    response = auth_client.get("/api/health")
    assert response.status_code == 200

    profile = response.get_json()["profile"]
    gewerk_profile = profile["gewerk_profile"]
    assert profile["profile_id"] == "sanitaer"
    assert profile["gewerk_name"] == "Sanitär"
    assert set(["profile_id", "gewerk_name", "document_types", "required_fields", "task_templates", "time_export_rules"]).issubset(gewerk_profile.keys())
    assert gewerk_profile["document_types"] == ["RECHNUNG", "WARTUNG"]
    assert gewerk_profile["required_fields"] == ["tenant", "kdnr", "doctype"]
    assert gewerk_profile["task_templates"] == ["Wartungstermin koordinieren"]
    reset_profiles_cache()
