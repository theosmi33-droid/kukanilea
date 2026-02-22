"""
app/ai_chat/views.py
Sichere KI-Assistenz für KUKANILEA (EPIC 7).
Setzt auf das "Conversation as Shortcut" Muster mit Confirm-Gate.
"""
import logging
from fastapi import APIRouter, Request, Form, Depends
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
async def handle_message(
    request: Request, 
    message: str = Form(...),
    ctx: SecurityContext = Depends(get_current_security_context)
):
    """
    Verarbeitet Nutzeranfragen und schlägt Aktionen vor.
    KEINE direkte DB-Mutation (Compliance: Human-in-the-loop).
    """
    logger.info(f"AI Chat (User: {ctx.user_id}) received: {message}")
    
    msg_lower = message.lower()
    
    # Heuristik-basierte Aktions-Erkennung (Vorbereitung für LLM-Integration)
    if any(k in msg_lower for k in ["aufgabe", "task", "todo"]):
        title = message.split("aufgabe", 1)[-1].strip() or "Neue Aufgabe"
        return templates.TemplateResponse(
            "ai_chat/shortcuts.html", 
            {"request": request, "action": "create_task", "params": {"title": title}}
        )
    
    # Fallback
    return templates.TemplateResponse(
        "ai_chat/shortcuts.html", 
        {"request": request, "action": "unknown"}
    )
