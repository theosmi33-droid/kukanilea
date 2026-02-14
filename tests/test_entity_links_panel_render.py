from __future__ import annotations

from pathlib import Path

import kukanilea_core_v3_fixed as core
from app import create_app
from app.entity_links.core import create_link
from app.knowledge.core import knowledge_note_create
from app.lead_intake.core import leads_create


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _client(tmp_path: Path):
    _init_core(tmp_path)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", READ_ONLY=False)
    with app.app_context():
        lead_id = leads_create(
            tenant_id="TENANT_A",
            source="manual",
            contact_name="A",
            contact_email="mail@example.com",
            contact_phone="+491111111111",
            subject="Lead <script>alert(1)</script>",
            message="GEHEIMER TEXT +491111111111",
        )
        note = knowledge_note_create(
            "TENANT_A",
            "dev",
            "",
            "Kontaktiere secret@example.com bald",
            "tag",
        )
        create_link(
            "TENANT_A",
            "lead",
            lead_id,
            "knowledge_note",
            str(note["chunk_id"]),
            "related",
            actor_user_id="dev",
        )
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "TENANT_A"
    return client, lead_id


def test_entity_links_panel_renders_sanitized_titles(tmp_path: Path) -> None:
    client, lead_id = _client(tmp_path)
    resp = client.get(f"/entity-links/lead/{lead_id}")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    assert "GEHEIMER TEXT" not in html
    assert "secret@example.com" not in html
    assert "[redacted-email]" in html
    assert "<script>" not in html


def test_entity_links_templates_do_not_use_safe_filter() -> None:
    root = Path(__file__).resolve().parents[1] / "templates" / "entity_links"
    assert root.exists()
    for tpl in sorted(root.rglob("*.html")):
        content = tpl.read_text(encoding="utf-8")
        assert "|safe" not in content
