from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

import app.web as webmod

from .pages.login_page import LoginPage
from .pages.navigation_page import NavigationPage

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("playwright") is None,
    reason="playwright not installed",
)

ARTIFACT_DIR = Path("output/playwright")


def _ensure_artifact_dir() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def _attach_request_id_collector(page):
    request_ids: set[str] = set()

    def _on_response(response):
        rid = str(response.headers.get("x-request-id") or "").strip()
        if rid:
            request_ids.add(rid)

    page.on("response", _on_response)
    return request_ids


def _write_request_ids(request_ids: set[str], filename: str) -> Path:
    _ensure_artifact_dir()
    out = ARTIFACT_DIR / filename
    out.write_text("\n".join(sorted(request_ids)), encoding="utf-8")
    return out


def _open_chat_widget(page) -> None:
    page.click("#chatWidgetBtn")
    page.evaluate(
        """
        const drawer = document.getElementById('chatDrawer');
        if (drawer && drawer.classList.contains('hidden')) drawer.classList.remove('hidden');
        """
    )
    page.wait_for_selector("#chatWidgetInput", state="visible")


@pytest.mark.e2e
def test_hardening_top_flows_smoke(
    monkeypatch: pytest.MonkeyPatch,
    page,
    base_url: str,
) -> None:
    _ensure_artifact_dir()
    request_ids = _attach_request_id_collector(page)

    # Keep AI deterministic and verify graceful handling on provider-down behavior.
    # The widget disables input when status endpoint reports unavailable, so keep
    # availability true and force an error response from chat processing instead.
    monkeypatch.setattr(webmod, "is_any_provider_available", lambda **_: True)
    monkeypatch.setattr(
        webmod,
        "ai_process_message",
        lambda **_: {
            "status": "error",
            "response": "Provider unavailable, fallback pending.",
            "conversation_id": "conv-hardening-e2e-1",
            "tool_used": [],
        },
    )

    login = LoginPage(page, base_url)
    nav = NavigationPage(page, base_url)

    # 1) Login
    login.goto()
    login.login("e2e_admin", "e2e_admin")
    page.screenshot(path=str(ARTIFACT_DIR / "flow-login.png"), full_page=True)

    # 2) CRM: create/search/open
    nav.open("/crm/customers")
    customer_name = "Smoke Customer 2026"
    page.fill("#createCustomerForm input[name='name']", customer_name)
    page.fill("#createCustomerForm input[name='vat_id']", "DE123")
    page.fill("#createCustomerForm input[name='notes']", "hardening smoke")
    page.click("#createCustomerForm button[type='submit']")
    page.wait_for_timeout(700)
    assert page.locator("#customersTable").first.is_visible()

    page.fill("#customerSearch input[name='q']", customer_name)
    page.click("#customerSearch button[type='submit']")
    page.wait_for_timeout(700)
    assert customer_name in (page.locator("#customersTable").text_content() or "")

    page.locator("#customersTable a", has_text="Öffnen").first.click()
    page.wait_for_load_state("networkidle")
    assert customer_name in (page.locator("body").text_content() or "")
    page.screenshot(path=str(ARTIFACT_DIR / "flow-crm.png"), full_page=True)

    # 3) Tasks: create/move status
    created = page.request.post(
        f"{base_url}/api/tasks/create",
        data={
            "title": "Hardening Task",
            "task_type": "GENERAL",
            "severity": "INFO",
            "details": "e2e",
        },
    )
    assert created.ok
    task_id = int((created.json() or {}).get("task_id") or 0)
    assert task_id > 0

    moved = page.request.post(
        f"{base_url}/api/tasks/{task_id}/move",
        data={"column": "done"},
    )
    assert moved.ok
    resolved = page.request.get(f"{base_url}/api/tasks?status=RESOLVED")
    assert resolved.ok
    resolved_ids = {int(item.get("id") or 0) for item in (resolved.json() or {}).get("tasks") or []}
    assert task_id in resolved_ids

    nav.open("/tasks")
    nav.expect_text("Tasks Kanban")
    page.screenshot(path=str(ARTIFACT_DIR / "flow-tasks.png"), full_page=True)

    # 4) Docs: import/search/open
    note_title = "Hardening Note 2026"
    note_created = page.request.post(
        f"{base_url}/api/knowledge/notes",
        data={"title": note_title, "body": "Dummy file content for smoke"},
    )
    assert note_created.ok

    search = page.request.get(f"{base_url}/api/knowledge/search?q=Hardening%20Note%202026")
    assert search.ok
    items = (search.json() or {}).get("items") or []
    assert items

    nav.open("/knowledge/notes")
    assert note_title in (page.locator("body").text_content() or "")
    page.screenshot(path=str(ARTIFACT_DIR / "flow-docs.png"), full_page=True)

    # 5) AI: send prompt and verify graceful error status
    nav.open("/")
    _open_chat_widget(page)
    assert page.locator("#chatWidgetSend").is_enabled()
    ai_res = page.request.post(f"{base_url}/api/ai/chat", data={"q": "health check"})
    assert ai_res.ok
    ai_payload = ai_res.json() or {}
    assert ai_payload.get("status") == "error"
    assert "unavailable" in str(ai_payload.get("message") or "").lower()
    assert page.locator("#chatWidgetSend").is_enabled()
    page.screenshot(path=str(ARTIFACT_DIR / "flow-ai.png"), full_page=True)

    req_file = _write_request_ids(request_ids, "hardening-request-ids.log")
    assert req_file.exists()
    assert req_file.read_text(encoding="utf-8").strip() != ""


@pytest.mark.e2e
def test_hardening_error_shell_navigation(page, base_url: str) -> None:
    _ensure_artifact_dir()

    login = LoginPage(page, base_url)
    login.goto()
    login.login("e2e_admin", "e2e_admin")

    page.goto(f"{base_url}/does-not-exist-hardening")
    page.wait_for_load_state("networkidle")

    body = page.locator("body").text_content() or ""
    assert "Fehler 404" in body
    assert page.locator("#goBack").is_visible()
    assert page.locator("#reloadPage").is_visible()
    assert page.locator("a", has_text="Dashboard").first.is_visible()
    page.screenshot(path=str(ARTIFACT_DIR / "flow-error-ux.png"), full_page=True)


@pytest.mark.e2e
def test_command_palette_placeholder_stub() -> None:
    pytest.skip("TODO: command palette/search UX benchmark test to be implemented with feature epic")
