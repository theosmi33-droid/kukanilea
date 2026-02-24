from locust import HttpUser, task, between

class EnduranceUser(HttpUser):
    wait_time = between(10, 30)  # Langsamere, stetige Last
    
    @task(5)
    def view_dashboard(self):
        self.client.get("/")
        
    @task(2)
    def check_health(self):
        self.client.get("/health")
        
    @task(1)
    def list_recent_events(self):
        self.client.get("/api/events?limit=50")
