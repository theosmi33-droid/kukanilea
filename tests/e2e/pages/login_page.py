from __future__ import annotations

from typing import Any


class LoginPage:
    def __init__(self, page: Any, base_url: str):
        self.page = page
        self.base_url = base_url

    def goto(self) -> None:
        self.page.goto(f"{self.base_url}/login")

    def login(self, username: str, password: str) -> None:
        self.page.fill("input[name='username']", username)
        self.page.fill("input[name='password']", password)
        self.page.click("button[type='submit']")
        self.page.wait_for_load_state("networkidle")
