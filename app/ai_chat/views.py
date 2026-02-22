"""
app/ai_chat/views.py
Flask-Routen für das AI-Chat Interface (Conversation as a Shortcut).
"""

from flask import Blueprint, render_template, request, g
from app.ai_chat.intent_parser import parse_user_intent

bp = Blueprint("ai_chat", __name__, url_prefix="/ai-chat")


@bp.get("/")
def chat_interface():
    """Rendert das Haupt-Chat-Interface."""
    return render_template("ai_chat/interface.html")


@bp.post("/message")
def handle_message():
    """Verarbeitet User-Messages via HTMX."""
    user_input = request.form.get("message", "").strip()
    intent = parse_user_intent(user_input)

    if intent["action"] == "create_task":
        # Rendert das Confirm-Gate (Partial Template)
        return render_template(
            "ai_chat/shortcuts.html",
            action=intent["action"],
            data=intent["data"]
        )

    # Fallback für unbekannte Intents
    return f'<div class="alert alert-info">{intent.get("message", "Unbekannter Fehler")}</div>'
