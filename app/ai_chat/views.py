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
from app.ai_chat.intent_parser import parse_intent

# ... (router and templates setup)

@router.post("/message")
async def handle_message(
    request: Request, 
    message: str = Form(...),
    ctx: SecurityContext = Depends(get_current_security_context)
):
    """
    Verarbeitet Nutzeranfragen via semantischem LLM-Parsing.
    KEINE direkte DB-Mutation (Compliance: Human-in-the-loop).
    """
    logger.info(f"AI Chat (User: {ctx.user_id}) received: {message}")
    
    # 1. Try Semantic LLM Parsing
    intent = await parse_intent(message)
    action = intent.get("action", "unknown")
    params = intent.get("params", {})

    # 2. Heuristic Fallback if LLM failed to identify action
    if action == "unknown":
        msg_lower = message.lower()
        if any(k in msg_lower for k in ["aufgabe", "task", "todo"]):
            action = "create_task"
            params = {"title": message.split("aufgabe", 1)[-1].strip() or "Neue Aufgabe"}

    # 3. Response Generation (Proposal based)
    return templates.TemplateResponse(
        "ai_chat/shortcuts.html", 
        {"request": request, "action": action, "params": params}
    )
