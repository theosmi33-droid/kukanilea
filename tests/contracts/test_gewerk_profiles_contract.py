from __future__ import annotations

from app.core.gewerk_profiles import build_action_ledger, flow_matrix, list_profiles


def test_gewerk_profile_contract_contains_20_profiles_and_required_fields():
    profiles = list_profiles()
    assert len(profiles) >= 20
    for profile in profiles:
        assert profile["profile_id"]
        assert profile["gewerk_name"]
        assert profile["standard_leistungen"]
        assert profile["dokumenttypen"]
        assert profile["pflichtfelder"]
        assert profile["task_templates"]
        assert profile["zeit_export_regeln"]
        assert set(profile["checklisten"]) == {"A", "B", "C", "D"}


def test_gewerk_flow_matrix_and_action_ledger_meet_2000x_target():
    matrix = flow_matrix()
    assert len(matrix) >= 20
    for row in matrix:
        assert row["flow_A"] == "PASS"
        assert row["flow_B"] == "PASS"
        assert row["flow_C"] == "PASS"
        assert row["flow_D"] == "PASS"

    ledger = build_action_ledger()
    assert ledger["target_met"] is True
    assert ledger["total_actions"] >= 2000
