from __future__ import annotations

import importlib.util

import pytest

from .pages.login_page import LoginPage
from .pages.navigation_page import NavigationPage

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("playwright") is None,
    reason="playwright not installed",
)


@pytest.mark.e2e
def test_tasks_kanban_page_loads(page, base_url: str) -> None:
    login = LoginPage(page, base_url)
    nav = NavigationPage(page, base_url)

    login.goto()
    login.login("e2e_admin", "e2e_admin")

    nav.open("/tasks")
    nav.expect_text("Tasks Kanban")
    assert page.locator("div.text-sm.font-semibold", has_text="Todo").first.is_visible()
