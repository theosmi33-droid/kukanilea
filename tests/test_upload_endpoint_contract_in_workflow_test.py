from pathlib import Path


def test_ui_workflow_targets_upload_route_and_file_input_contract():
    test_py = Path("tests/e2e/test_ui_workflow.py").read_text(encoding="utf-8")
    assert 'page.goto(f"{server}/upload")' in test_py
    assert "page.set_input_files('input[name=\"file\"]'" in test_py

