from pathlib import Path


def test_ui_workflow_blocked_upload_path_checks_presence_not_visibility():
    test_py = Path("tests/e2e/test_ui_workflow.py").read_text(encoding="utf-8")
    assert "if upload_blocked:" in test_py
    assert "to_have_count(1)" in test_py

