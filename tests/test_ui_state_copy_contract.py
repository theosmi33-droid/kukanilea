from pathlib import Path


def test_dashboard_uses_shared_state_panels_for_empty_states() -> None:
    html = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
    assert "components/state_panel.html" in html
    assert "Noch keine Belege im Archiv" in html
    assert "Review-Postkorb ist leer" in html


def test_upload_handles_partial_and_error_language() -> None:
    html = Path("app/templates/upload.html").read_text(encoding="utf-8")
    assert "Teilweise abgeschlossen" in html
    assert "Upload konnte nicht abgeschlossen werden" in html
    assert "Keine Verbindung zum Upload-Service" in html


def test_tasks_and_projects_show_degraded_and_empty_copy() -> None:
    tasks = Path("app/templates/tasks.html").read_text(encoding="utf-8")
    kanban = Path("app/templates/kanban.html").read_text(encoding="utf-8")
    assert "Eingeschränkter Modus" in tasks
    assert "Keine offenen Aufgaben" in tasks
    assert "Noch keine Spalten vorhanden" in kanban
