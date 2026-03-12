from __future__ import annotations

from pathlib import Path

README = Path("README.md")
QUICKSTART = Path("docs/dev/BOOTSTRAP_QUICKSTART.md")
CHECKLIST = Path("docs/dev/PIPELINE_REPRO_CHECKLIST.md")
RUNTIME_CONFIG = Path("app/config.py")


def _read(path: Path) -> str:
    assert path.exists(), f"missing: {path}"
    return path.read_text(encoding="utf-8")


def test_repro_docs_exist() -> None:
    assert README.exists()
    assert QUICKSTART.exists()
    assert CHECKLIST.exists()
    assert RUNTIME_CONFIG.exists()


def test_readme_data_location_tracks_runtime_user_data_root_contract() -> None:
    readme = _read(README)
    runtime_config = _read(RUNTIME_CONFIG)

    assert "## Data location" in readme
    assert "KUKANILEA_USER_DATA_ROOT" in readme
    assert "KUKANILEA_USER_DATA_ROOT" in runtime_config
    assert "user_data_dir(\"KUKANILEA\"" in runtime_config


def test_readme_includes_quickstart_under_10_minutes() -> None:
    text = _read(README)
    assert "Quickstart (<10 min)" in text
    assert "scripts/dev_bootstrap.sh" in text
    assert "scripts/dev_run.sh" in text


def test_readme_keeps_token_saver_workflow() -> None:
    text = _read(README)
    assert "Token-saver Workflow" in text
    assert "rg -n" in text


def test_readme_includes_tool_interface_verification() -> None:
    text = _read(README)
    assert "Tool Interface Verification" in text
    assert "python scripts/dev/verify_tools.py" in text


def test_checklist_contains_standard_flow() -> None:
    text = _read(CHECKLIST)
    assert "## Standardablauf" in text
    for marker in [
        "Clone + bootstrap",
        "Dev-Start",
        "Healthcheck",
        "Evidence Gate",
    ]:
        assert marker in text


def test_checklist_contains_troubleshooting_matrix() -> None:
    text = _read(CHECKLIST)
    assert "## Troubleshooting-Matrix" in text
    assert "pytest not found" in text
    assert "Playwright browser missing" in text


def test_checklist_contains_copy_paste_bundle() -> None:
    text = _read(CHECKLIST)
    assert "## Copy/Paste Command Bundle" in text
    assert "bash scripts/dev/pr_quality_guard.sh --ci" in text
    assert "scripts/ops/launch_evidence_gate.sh" in text


def test_checklist_has_success_criteria_and_ownership() -> None:
    text = _read(CHECKLIST)
    assert "## Success Criteria" in text
    assert "## Ownership" in text
    assert "dev-ci" in text
