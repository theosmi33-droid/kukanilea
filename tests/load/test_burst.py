from locust import HttpUser, task, between
import io

class BurstUser(HttpUser):
    wait_time = between(1, 3)  # Schnellere Requests
    
    @task(5)
    def rapid_search(self):
        """User macht schnelle Suchen (simuliert Autocomplete)"""
        for term in ["a", "ab", "abc"]:
            self.client.get(f"/api/search?q={term}")
    
    @task(3)
    def upload_document(self):
        """User lädt Dokument hoch (OCR-Trigger)"""
        # Create a dummy PDF in memory
        dummy_file = io.BytesIO(b"%PDF-1.4
1 0 obj
<< /Title (Test) >>
endobj
trailer
<< /Root 1 0 R >>
%%EOF")
        self.client.post("/api/documents/upload", files={
            "file": ("sample.pdf", dummy_file, "application/pdf")
        })
