from __future__ import annotations

from app.web import TOOL_ACTION_TEMPLATES
from app.contracts.tool_contracts import (
    TOOL_LEGACY_ALIASES,
    contract_tool_response_label,
    normalize_contract_tool_slug,
)


def test_legacy_aliases_are_normalized_to_canonical_tools() -> None:
    assert normalize_contract_tool_slug("projekte") == "projects"
    assert normalize_contract_tool_slug("emailpostfach") == "email"
    assert normalize_contract_tool_slug("zeiterfassung") == "time"
    assert normalize_contract_tool_slug("mail") == "email"


def test_canonical_tool_labels_are_preferred_for_canonical_requests(auth_client) -> None:
    projects_summary = auth_client.get("/api/projects/summary")
    assert projects_summary.status_code == 200
    assert projects_summary.get_json()["tool"] == "projects"

    email_health = auth_client.get("/api/email/health")
    assert email_health.status_code in {200, 503}
    assert email_health.get_json()["tool"] == "email"

    time_summary = auth_client.get("/api/time/summary")
    assert time_summary.status_code == 200
    assert time_summary.get_json()["tool"] == "time"


def test_legacy_alias_requests_keep_legacy_response_labels(auth_client) -> None:
    projekte = auth_client.get("/api/projekte/summary")
    assert projekte.status_code == 200
    assert projekte.get_json()["tool"] == "projekte"

    postfach = auth_client.get("/api/emailpostfach/summary")
    assert postfach.status_code == 200
    assert postfach.get_json()["tool"] == "emailpostfach"

    zeiterfassung = auth_client.get("/api/zeiterfassung/health")
    assert zeiterfassung.status_code in {200, 503}
    assert zeiterfassung.get_json()["tool"] == "zeiterfassung"


def test_alias_map_is_single_source_of_truth_for_response_labels() -> None:
    for alias, canonical in TOOL_LEGACY_ALIASES.items():
        normalized = normalize_contract_tool_slug(alias)
        assert normalized == canonical
        assert contract_tool_response_label(alias, normalized) == alias
        assert contract_tool_response_label(canonical, normalized) == canonical


def test_actions_templates_expose_only_canonical_names_for_selected_legacy_pairs() -> None:
    assert "projects" in TOOL_ACTION_TEMPLATES
    assert "time" in TOOL_ACTION_TEMPLATES
    assert "email" in TOOL_ACTION_TEMPLATES

    assert "projekte" not in TOOL_ACTION_TEMPLATES
    assert "zeiterfassung" not in TOOL_ACTION_TEMPLATES
    assert "mail" not in TOOL_ACTION_TEMPLATES


def test_legacy_alias_actions_routes_normalize_to_canonical_templates(auth_client) -> None:
    projects = auth_client.get("/api/projects/actions")
    assert projects.status_code == 200
    assert projects.get_json().get("tool") == "projects"

    projekte = auth_client.get("/api/projekte/actions")
    assert projekte.status_code == 200
    assert projekte.get_json().get("tool") == "projects"

    time_tool = auth_client.get("/api/time/actions")
    assert time_tool.status_code == 200
    assert time_tool.get_json().get("tool") == "time"

    zeiterfassung = auth_client.get("/api/zeiterfassung/actions")
    assert zeiterfassung.status_code == 200
    assert zeiterfassung.get_json().get("tool") == "time"

    email = auth_client.get("/api/email/actions")
    assert email.status_code == 200
    assert email.get_json().get("tool") == "email"

    mail = auth_client.get("/api/mail/actions")
    assert mail.status_code == 200
    assert mail.get_json().get("tool") == "email"
