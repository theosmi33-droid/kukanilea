from pathlib import Path


def test_healthcheck_supports_skip_pytest_fallback():
    script = Path("scripts/ops/healthcheck.sh").read_text(encoding="utf-8")
    assert "--skip-pytest" in script
    assert "continuing outside CI mode" in script
    assert "skipping HTTP route probes" in script
    assert "e2e.mode=" in script
    assert "skip_python_e2e" in script
    assert "CI mode enabled" in script
    assert "scripts/dev/doctor.sh --strict --ci" in script


def test_launch_evidence_handles_missing_origin_main_without_fatal_fetch():
    script = Path("scripts/ops/launch_evidence_gate.sh").read_text(encoding="utf-8")
    assert "git show-ref --verify --quiet refs/remotes/origin/main" in script
    assert "origin/main unavailable in local clone" in script
    assert "git fetch origin --prune" not in script


def test_launch_evidence_does_not_use_literal_gate7_output_dir_path():
    script = Path("scripts/ops/launch_evidence_gate.sh").read_text(encoding="utf-8")
    assert "base = Path('$GATE7_OUTPUT_DIR')" not in script
    assert "GATE7_OUTPUT_DIR=\\\"$GATE7_OUTPUT_DIR\\\" \\\"$PYTHON\\\" - <<'PY'" not in script
    assert "base = Path(os.environ['GATE7_OUTPUT_DIR'])" in script


def test_healthcheck_checks_ops_release_levers():
    script = Path("scripts/ops/healthcheck.sh").read_text(encoding="utf-8")
    assert "ops settings defaults" in script
    assert "backup/restore verification hooks" in script
    assert "external_apis_enabled" in script
    assert "memory_retention_days" in script
