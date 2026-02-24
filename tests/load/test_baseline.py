from locust import HttpUser, task, between, events
import logging

class KukanileaPowerUser(HttpUser):
    """
    Simuliert einen Power-User, der intensiv mit CRM, Tasks und AI-Suche arbeitet.
    Ziel: Verifikation des Performance-Budgets (< 200ms).
    """
    wait_time = between(1, 5) 
    
    def on_start(self):
        """Initialer Login und Session-Setup."""
        with self.client.post("/login", data={
            "username": "admin",
            "password": "admin"
        }, catch_response=True, allow_redirects=False) as response:
            if response.status_code == 302:
                response.success()
                logging.info(f"Login erfolgreich (302) -> {response.headers.get('Location')}")
            elif response.status_code == 200 and "Dashboard" in response.text:
                response.success()
                logging.info("Login erfolgreich (200 + Dashboard found)")
            else:
                response.failure(f"Login fehlgeschlagen: {response.status_code}")

    @task(5)
    def view_dashboard(self):
        """Häufigster Zugriff: Das Haupt-Dashboard."""
        self.client.get("/", name="UI: Dashboard")

    @task(3)
    def search_knowledge(self):
        """Simuliert eine KI-gestützte Suche (FTS5 + RAG)."""
        self.client.post("/api/search", json={
            "query": "Rechnung Vaillant",
            "limit": 10
        }, name="API: Global Search")

    @task(2)
    def list_tasks(self):
        """Abruf der Kanban-Tasks."""
        self.client.get("/api/tasks", name="API: List Tasks")

    @task(1)
    def check_ai_status(self):
        """Polling des AI-Status."""
        self.client.get("/api/ai/status", name="API: AI Status")

    @task(1)
    def view_crm_customers(self):
        """Anzeige der Kundenliste."""
        self.client.get("/crm/customers", name="UI: CRM Customers")
