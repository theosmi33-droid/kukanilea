"""
app/ui/onboarding.py
HTMX-basierter Onboarding Wizard für die 110% KUKANILEA Vision.
"""
import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

import json
from app.database import get_db_connection

router = APIRouter(prefix="/ui/onboarding", tags=["UX", "Onboarding"])
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger("kukanilea.onboarding")

# Branchenspezifische Vorlagen (EPIC 6)
VERTICAL_DATA = {
    "dach": [
        {"name": "Rapport: Dachinspektion", "content": {"fields": ["Ziegelzustand", "Firstprüfung", "Regenrinne"]}},
        {"name": "Aufmaß: Steildach", "content": {"unit": "m2", "factors": ["Neigung", "Überlappung"]}}
    ],
    "shk": [
        {"name": "Protokoll: Wartung Gastherme", "content": {"steps": ["Abgasmessung", "Dichtheitsprüfung", "Filterreinigung"]}},
        {"name": "Materialliste: Badsanierung", "content": {"categories": ["Rohre", "Armaturen", "Keramik"]}}
    ],
    "facility": [
        {"name": "Checkliste: Objektbegehung", "content": {"areas": ["Leuchtmittel", "Notausgänge", "Heizraum"]}},
        {"name": "Störungsmeldung: Aufzug", "content": {"priority_levels": ["Normal", "Hoch", "Notfall"]}}
    ]
}

@router.get("/", response_class=HTMLResponse)
async def onboarding_wizard(request: Request):
    """Rendert den Setup-Wizard beim ersten Start."""
    return templates.TemplateResponse("onboarding/wizard.html", {"request": request})

@router.post("/setup")
async def apply_vertical_kit(request: Request, vertical: str = Form(...)):
    """
    Injiziert branchenspezifische Vorlagen in die lokale SQLite-DB.
    Leitet den Nutzer danach via HTMX auf das CRM-Dashboard um.
    """
    logger.info(f"Applying Vertical Kit: {vertical}")
    
    if vertical in VERTICAL_DATA:
        conn = get_db_connection()
        try:
            # Lösche alte Templates für sauberen Start (Idempotenz)
            conn.execute("DELETE FROM templates WHERE vertical = ?", (vertical,))
            
            for item in VERTICAL_DATA[vertical]:
                conn.execute(
                    "INSERT INTO templates (vertical, name, content_json) VALUES (?, ?, ?)",
                    (vertical, item["name"], json.dumps(item["content"]))
                )
            conn.commit()
            logger.info(f"Successfully seeded {len(VERTICAL_DATA[vertical])} templates for {vertical}.")
        except Exception as e:
            logger.error(f"Seeding failed: {e}")
            conn.rollback()
        finally:
            conn.close()

    # HTMX Redirect-Header, um den Client auf das Dashboard zu leiten
    response = Response(status_code=204)
    response.headers["HX-Redirect"] = "/crm/"
    return response
