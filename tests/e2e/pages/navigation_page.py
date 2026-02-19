from __future__ import annotations

from typing import Any


class NavigationPage:
    def __init__(self, page: Any, base_url: str):
        self.page = page
        self.base_url = base_url

    def open(self, path: str) -> None:
        self.page.goto(f"{self.base_url}{path}")
        self.page.wait_for_load_state("networkidle")

    def expect_text(self, text: str) -> None:
        assert self.page.locator("body").text_content() and text in str(
            self.page.locator("body").text_content()
        )
