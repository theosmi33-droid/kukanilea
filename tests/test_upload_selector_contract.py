from pathlib import Path


def test_upload_template_exposes_primary_and_legacy_selector_contract():
    html = Path("app/templates/upload.html").read_text(encoding="utf-8")
    assert 'id="startAnalysis"' in html
    assert 'input type="file" id="file" name="file"' in html
    assert 'id="uploadStatePill"' in html
    assert 'id="stagedCounter"' in html
    assert 'id="rejectedFiles"' in html
    assert 'id="parkStaging"' in html
    assert 'id="uploadHistoryList"' in html
    assert 'id="uploadCollaborationState"' in html
