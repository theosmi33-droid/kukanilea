from pathlib import Path

from app.core import logic


def test_process_with_answers_rejects_use_existing_outside_tenant(tmp_path, monkeypatch):
    monkeypatch.setattr(logic, "BASE_PATH", tmp_path / "base")
    monkeypatch.setattr(logic, "EINGANG", tmp_path / "eingang")
    monkeypatch.setattr(logic, "PENDING_DIR", tmp_path / "pending")
    monkeypatch.setattr(logic, "DONE_DIR", tmp_path / "done")
    monkeypatch.setattr(logic, "ZWISCHENABLAGE", tmp_path / "zwischen")
    monkeypatch.setattr(logic, "DB_PATH", tmp_path / "db.sqlite3")
    monkeypatch.setattr(logic, "_DB_INITIALIZED", False)

    src = tmp_path / "incoming.txt"
    src.write_text("demo", encoding="utf-8")

    outside_dir = tmp_path / "outside"
    outside_dir.mkdir(parents=True)

    answers = {
        "tenant": "acme",
        "kdnr": "1234",
        "name": "Max Mustermann",
        "addr": "Hauptstrasse 1",
        "plzort": "12345 Berlin",
        "doctype": "RECHNUNG",
        "document_date": "2025-10-24",
        "use_existing": str(outside_dir),
    }

    folder, target, created_new = logic.process_with_answers(src, answers)

    tenant_dir = logic.BASE_PATH / "acme"
    assert created_new is True
    assert folder.exists() and folder.is_dir()
    assert target.exists() and target.is_file()
    assert logic._is_within_dir(folder, tenant_dir)
    assert folder.resolve() != outside_dir.resolve()
