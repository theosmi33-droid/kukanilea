from pathlib import Path


def test_upload_template_wires_start_button_to_upload_action():
    html = Path("app/templates/upload.html").read_text(encoding="utf-8")
    assert 'const startBtn = document.getElementById("startAnalysis");' in html
    assert "startBtn.addEventListener(\"click\", uploadAction);" in html

