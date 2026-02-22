"""
app/ai_chat/views.py
Sichere KI-Assistenz für KUKANILEA (EPIC 7).
Setzt auf das "Conversation as Shortcut" Muster mit Confirm-Gate.
"""
import logging
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.authz import SecurityContext, get_current_security_context

router = APIRouter(prefix="/ai-chat", tags=["AI", "UX"])
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger("kukanilea.aichat")

@router.get("/", response_class=HTMLResponse)
async def chat_interface(request: Request):
    """Rendert das KI-Chat-Interface."""
    return templates.TemplateResponse("ai_chat/interface.html", {"request": request})

@router.post("/message")
async def handle_message(request: Request, message: str = Form(...)):
    """
    Verarbeitet Nutzeranfragen und schlägt Aktionen vor.
    KEINE direkte DB-Mutation (Compliance: Human-in-the-loop).
    """
    logger.info(f"AI Chat received: {message}")
    
    # Simulation einer KI-Analyse (EPIC 7)
    if "aufmaß" in message.lower() and "müller" in message.lower():
        # Die KI schlägt ein ausgefülltes Formular vor
        return HTMLResponse("""
            <div class="bg-blue-50 p-4 rounded border border-blue-200 mt-4">
                <p class="text-sm font-bold text-blue-800">KI-Vorschlag:</p>
                <p class="text-sm mb-4">Ich habe ein neues Aufmaß für 'Müller' vorbereitet.</p>
                <button 
                    hx-get="/crm/details/1" 
                    hx-target="#main-content"
                    class="bg-blue-600 text-white px-4 py-2 rounded text-sm font-bold">
                    Formular prüfen & speichern
                </button>
            </div>
        """)
    
    return HTMLResponse(f"""
        <div class="p-2 text-gray-600 italic mt-2">
            KI: Ich habe verstanden: "{message}". Aktuell kann ich nur Aufmaße vorbereiten.
        </div>
    """)
