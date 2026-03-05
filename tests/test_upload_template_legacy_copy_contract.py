from pathlib import Path


def test_legacy_upload_template_keeps_same_start_button_contract():
    html = Path("app/templates/upload/index.html").read_text(encoding="utf-8")
    assert 'id="startAnalysis"' in html
    assert 'const startBtn = document.getElementById("startAnalysis");' in html

