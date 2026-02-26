import random

from locust import HttpUser, between, task


class KukanileaUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Simulates user login at the start of the session."""
        self.csrf_token = self.get_csrf()
        self.client.post(
            "/login",
            data={
                "username": "admin",
                "password": "admin",  # pragma: allowlist secret
                "csrf_token": self.csrf_token,
            },
        )

    def get_csrf(self):
        """Fetches the CSRF token from the login page."""
        response = self.client.get("/login")
        # Extract token from meta tag: <meta name="csrf-token" content="...">
        import re

        match = re.search(r'name="csrf-token" content="([^"]+)"', response.text)
        return match.group(1) if match else ""

    @task(3)
    def view_dashboard(self):
        self.client.get("/")

    @task(2)
    def search_query(self):
        queries = ["Rechnung", "Angebot", "Müller", "K12345"]
        q = random.choice(queries)
        headers = {"X-CSRF-Token": self.csrf_token}
        self.client.post("/api/search", json={"q": q}, headers=headers)

    @task(1)
    def chat_interaction(self):
        headers = {"X-CSRF-Token": self.csrf_token}
        self.client.post(
            "/api/chat", json={"q": "Wer ist Kunde Müller?"}, headers=headers
        )

    @task(1)
    def view_mesh(self):
        self.client.get("/admin/mesh")
