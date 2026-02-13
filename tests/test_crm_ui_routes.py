from __future__ import annotations

import io
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


def _auth(client, tenant: str = "TENANT_A") -> None:
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = tenant


def test_crm_pages_and_partials_return_200(tmp_path: Path) -> None:
    _init_core(tmp_path)
    customer_id = core.customers_create("TENANT_A", "UI Kunde")
    core.contacts_create(
        "TENANT_A", customer_id, "Max Mustermann", email="max@example.com"
    )
    deal_id = core.deals_create("TENANT_A", customer_id, "UI Deal", stage="lead")
    quote = core.quotes_create_from_deal("TENANT_A", deal_id)

    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _auth(client)

    for path in [
        "/crm/customers",
        f"/crm/customers/{customer_id}",
        "/crm/deals",
        "/crm/quotes",
        "/crm/emails/import",
        "/crm/_customers_table",
        f"/crm/_customer_contacts/{customer_id}",
        f"/crm/_customer_deals/{customer_id}",
        f"/crm/_customer_quotes/{customer_id}",
        f"/crm/_customer_emails/{customer_id}",
        "/crm/_deals_pipeline",
        "/crm/_quotes_table",
        f"/crm/quotes/{quote['id']}",
    ]:
        res = client.get(path)
        assert res.status_code == 200, path

    assert b"CRM" in client.get("/crm/customers").data
    assert b"Kontakte" in client.get(f"/crm/_customer_contacts/{customer_id}").data


def test_crm_email_import_page_upload_flow(tmp_path: Path) -> None:
    _init_core(tmp_path)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _auth(client)

    eml = b"From: sender@example.com\nTo: receiver@example.com\nSubject: UI\n\nBody"
    resp = client.post(
        "/api/emails/import",
        data={"file": (io.BytesIO(eml), "sample.eml")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    page = client.get("/crm/emails/import")
    assert page.status_code == 200
    assert b"E-Mail Import" in page.data
