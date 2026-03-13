from pathlib import Path


def test_upload_template_wires_start_button_to_upload_action():
    html = Path("app/templates/upload.html").read_text(encoding="utf-8")
    assert 'const startBtn = document.getElementById("startAnalysis");' in html
    assert "startBtn.addEventListener(\"click\", uploadAction);" in html
    assert "const appendStagedFiles = (incoming) => {" in html
    assert "dropZone.dataset.hasFiles = stagedFiles.length > 0 ? \"1\" : \"0\";" in html
    assert "const persistDraftFiles = async (files) => {" in html
    assert "const loadDraftFiles = async () => {" in html
    assert "const uploadHistoryKey = \"kuka_upload_history_v1\";" in html
    assert "const uploadEditorKey = \"kuka_upload_editor_lock\";" in html
    assert "_renderUploadHistory();" in html
    assert "_renderEditorLock();" in html
