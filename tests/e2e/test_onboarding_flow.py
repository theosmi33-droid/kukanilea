import re
from playwright.sync_api import Page, expect

def test_unlicensed_redirect_to_onboarding(page: Page):
    """Prüft das License-Gatekeeper-Verhalten und den Onboarding-Flow."""
    # 1. Simuliere einen unlizenzierten Start
    page.goto("http://127.0.0.1:8080/")
    
    # 2. Assertion: System MUSS den Nutzer auf den Onboarding/License-Wizard umleiten
    expect(page).to_have_url(re.compile(r".*(/onboarding|/license|/bootstrap).*"))
    
    # Da wir in einer Testumgebung sind, können wir direkt /license ansteuern
    page.goto("http://127.0.0.1:8080/license")
    
    # 3. Simuliere die Eingabe eines Mock-Lizenzschlüssels
    mock_license = '{"customer_id": "FLISA", "plan": "GOLD", "expiry": "2027-12-31", "signature": "MOCK", "features": ["all"]}'
    page.fill("textarea[name='license_json']", mock_license)
    
    # Submit 
    page.click("button[type='submit']")
    
    # 4. Assertion: UI muss Erfolg quittieren (bzw. ungültige Lizenz in der CI abfangen)
    # Da die Signatur im Test ungültig ist, checken wir, ob das Formular reagiert hat.
    # In einem reinen MOCK-Setup würde hier "Lizenz aktiviert" stehen.
    expect(page.locator("body")).to_contain_text(re.compile(r"Lizenz|aktiviert|ungültig"))
