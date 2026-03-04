import random
import re
from locust import HttpUser, between, task

class KukanileaFleetUser(HttpUser):
    wait_time = between(0.5, 2)

    def on_start(self):
        """Simulates user login at the start of the session."""
        self.csrf_token = self.get_csrf()
        # Mock login - we assume 'admin' exists or use credentials bypass for stress
        self.client.post(
            "/login",
            data={
                "username": "admin",
                "password": "admin",
                "csrf_token": self.csrf_token,
            },
        )

    def get_csrf(self):
        response = self.client.get("/login")
        match = re.search(r'name="csrf-token" content="([^"]+)"', response.text)
        return match.group(1) if match else "bench-token"

    @task(5)
    def dashboard(self):
        self.client.get("/")

    @task(3)
    def messenger_hub(self):
        self.client.get("/messenger")

    @task(2)
    def mail_hub(self):
        self.client.get("/mail")

    @task(4)
    def chatbot_compact(self):
        headers = {"X-CSRF-Token": self.csrf_token, "Content-Type": "application/json"}
        msg = random.choice(["Hallo", "Status Messenger?", "Hilf mir bei Mail", "Suche Rechnungen"])
        self.client.post("/api/chat/compact", json={"message": msg, "current_context": "/"}, headers=headers)

    @task(2)
    def search_docs(self):
        headers = {"X-CSRF-Token": self.csrf_token, "Content-Type": "application/json"}
        q = random.choice(["Müller", "Rechnung", "Bauvorhaben"])
        self.client.post("/api/search", json={"query": q}, headers=headers)

    @task(1)
    def mock_upload(self):
        # Stressing the endpoint that handles multipart/form-data
        self.client.post("/upload", data={"csrf_token": self.csrf_token}, files={"file": ("test.txt", "stress data content")})

    @task(1)
    def system_status(self):
        self.client.get("/api/system/status")
