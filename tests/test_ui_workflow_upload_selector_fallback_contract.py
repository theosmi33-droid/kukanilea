from pathlib import Path


def test_ui_workflow_uses_start_analysis_with_legacy_fallback():
    test_py = Path("tests/e2e/test_ui_workflow.py").read_text(encoding="utf-8")
    assert 'upload_cta = page.locator("#startAnalysis")' in test_py
    assert 'upload_cta = page.locator("#btn-upload")' in test_py

