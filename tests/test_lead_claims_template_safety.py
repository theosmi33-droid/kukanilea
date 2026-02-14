from __future__ import annotations

from pathlib import Path

import kukanilea_core_v3_fixed as core
from app import create_app


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_no_safe_filter_in_lead_templates() -> None:
    root = Path(__file__).resolve().parents[1] / "templates" / "lead_intake"
    assert root.exists()
    for tpl in sorted(root.rglob("*.html")):
        content = tpl.read_text(encoding="utf-8")
        assert "|safe" not in content


def test_claim_panel_escapes_user_content(tmp_path: Path) -> None:
    _init_core(tmp_path)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", READ_ONLY=False)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "<script>alert(1)</script>"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "TENANT_A"

    created = client.post(
        "/api/leads",
        json={
            "source": "manual",
            "contact_name": "A",
            "subject": "Lead",
            "message": "M",
        },
    )
    lead_id = (created.get_json() or {}).get("lead_id")
    assert lead_id

    claim_resp = client.post(f"/leads/{lead_id}/claim", headers={"HX-Request": "true"})
    assert claim_resp.status_code == 200
    text = claim_resp.get_data(as_text=True)
    assert "<script>alert(1)</script>" not in text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text
