import os
from typing import Iterable

import pytest
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, expect

from tests.e2e.test_ui_workflow import server

ROUTES: tuple[str, ...] = (
    "/dashboard",
    "/upload",
    "/projects",
    "/tasks",
    "/messenger",
    "/email",
    "/calendar",
    "/time",
    "/visualizer",
    "/settings",
)



def _target_actions() -> int:
    raw = os.getenv("VR_ACTION_TARGET", "2400")
    try:
        parsed = int(raw)
    except ValueError:
        parsed = 2400
    return max(2400, parsed)



def _stable_goto(page: Page, url: str, *, attempts: int = 3) -> None:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_load_state("networkidle", timeout=15000)
            expect(page.locator("body")).not_to_contain_text("wird geladen")
            return
        except PlaywrightTimeoutError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error



def _login(page: Page, base_url: str) -> None:
    _stable_goto(page, f"{base_url}/login")
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "admin")
    page.click('button[type="submit"]')
    expect(page).to_have_url(f"{base_url}/dashboard")


@pytest.mark.e2e
def test_visual_regression_baselines_and_diff_gate(page: Page, server: str) -> None:
    """Runs >=2400 deterministic actions and verifies screenshot baselines."""
    _login(page, server)

    action_target = _target_actions()
    action_count = 0
    route_cycle: Iterable[str] = ROUTES

    while action_count < action_target:
        for route in route_cycle:
            if action_count >= action_target:
                break
            _stable_goto(page, f"{server}{route}")
            expect(page.locator("#main-content")).to_be_visible()
            action_count += 1

            if action_count % 240 == 0:
                expect(page.locator("#main-content")).to_have_screenshot(
                    f"baseline-{route.strip('/')}.png",
                    animations="disabled",
                    max_diff_pixel_ratio=0.02,
                )

    assert action_count >= 2400


@pytest.mark.e2e
def test_flaky_navigation_stabilization(page: Page, server: str) -> None:
    """Stabilizes known flaky route transitions with deterministic retry navigation."""
    _login(page, server)

    for route in ROUTES:
        for _ in range(5):
            _stable_goto(page, f"{server}{route}")
            expect(page.locator("#main-content[data-page-ready='1']")).to_be_visible(timeout=15000)
