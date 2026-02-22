import re
import pytest
from fastapi.testclient import TestClient
from kukanilea_app import app

client = TestClient(app)

def test_csp_header_enforces_offline_policy():
    """Verify that CSP headers are present and restrictive."""
    response = client.get("/")
    assert response.status_code == 200
    csp = response.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp
    assert "connect-src 'self'" in csp

def test_no_rogue_external_urls_in_rendered_html():
    """Scan HTML for unauthorized external resource links."""
    response = client.get("/")
    html = response.text
    
    # Authorized prototyping allowlist (CDN for Tailwind/HTMX)
    # Note: In EPIC 5 (Prod), these must be bundled locally.
    allowlist = [
        "https://cdn.tailwindcss.com",
        "https://unpkg.com/htmx.org"
    ]
    
    # Find all src/href URLs
    urls = re.findall(r'(?:src|href)=["\'](https?://.*?)["\']', html)
    
    for url in urls:
        is_authorized = any(url.startswith(allowed) for allowed in allowlist)
        assert is_authorized, f"SECURITY VIOLATION: Unauthorized external resource found: {url}"
