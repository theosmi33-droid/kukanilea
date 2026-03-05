from pathlib import Path


def test_healthcheck_supports_skip_pytest_fallback():
    script = Path("scripts/ops/healthcheck.sh").read_text(encoding="utf-8")
    assert "--skip-pytest" in script
    assert "continuing outside CI mode" in script
    assert "skipping HTTP route probes" in script
    assert "CI mode enabled" in script
    assert "scripts/dev/doctor.sh --strict --ci" in script


def test_launch_evidence_handles_missing_origin_main_without_fatal_fetch():
    script = Path("scripts/ops/launch_evidence_gate.sh").read_text(encoding="utf-8")
    assert "git show-ref --verify --quiet refs/remotes/origin/main" in script
    assert "origin/main unavailable in local clone" in script
    assert "git fetch origin --prune" not in script
