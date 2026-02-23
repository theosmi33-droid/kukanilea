"""
app/ai_chat/views.py
Hybrid Routes (FastAPI + Flask) für das AI-Chat Interface.
Supports both legacy Flask tests/core and modern FastAPI desktop app.
"""

from typing import Any

# --- FastAPI Implementation ---
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.concurrency import run_in_threadpool

from app.ai_chat.engine import ask_local_ai
from app.ai_chat.intent_parser import parse_user_intent
from app.ai.ollama_client import ollama_is_available

from fastapi import APIRouter, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.concurrency import run_in_threadpool
import shutil
import os

from app.ai_chat.engine import ask_local_ai
from app.ai_chat.intent_parser import parse_user_intent
from app.ai.ollama_client import ollama_is_available
from app.autonomy.ocr import process_dirty_note

router = APIRouter(prefix="/ai-chat", tags=["AI", "Chat"])
templates = Jinja2Templates(directory="templates")

# ... (health, transcribe routes)

@router.post("/upload-vision", response_class=HTMLResponse)
async def upload_vision(request: Request, file: UploadFile = File(...)) -> Any:
    """Verarbeitet Bild-Uploads für lokale OCR-Extraktion."""
    # 1. Save temp file
    temp_path = f"instance/temp_{file.filename}"
    os.makedirs("instance", exist_ok=True)
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 2. Process via OCR + LLM (in threadpool)
    result_json = await run_in_threadpool(process_dirty_note, temp_path)
    
    # Cleanup
    if os.path.exists(temp_path):
        os.remove(temp_path)

    # 3. Parse JSON result safely
    import json
    try:
        data = json.loads(result_json) if isinstance(result_json, str) else result_json
    except:
        data = {"error": "Extraktion fehlgeschlagen", "raw": str(result_json)}

    # 4. Render Partial
    return templates.TemplateResponse(request, "ai_chat/partials/vision_result.html", {
        "filename": file.filename,
        "data": data
    })

async def handle_message(request: Request, message: str = Form("")) -> Any:
    """Verarbeitet User-Messages via HTMX (FastAPI) ohne den Event-Loop zu blockieren."""
    return await _process_message_logic_async(request, message)


# --- Flask Implementation ---
from flask import Blueprint, render_template, request, g, session

bp = Blueprint("ai_chat", __name__, url_prefix="/ai-chat")


@bp.get("/")
def flask_chat_interface() -> Any:
    """Rendert das Haupt-Chat-Interface (Flask)."""
    return render_template("ai_chat/interface.html")


@bp.post("/message")
def flask_handle_message() -> Any:
    """Verarbeitet User-Messages via HTMX (Flask)."""
    user_input = request.form.get("message", "").strip()
    return _process_message_logic(None, user_input, is_flask=True)


# --- Shared Logic ---
async def _process_message_logic_async(req: Request, user_input: str) -> Any:
    """Async wrapper for the processing logic using threadpool."""
    if not user_input:
        return HTMLResponse("")

    tenant_id = "KUKANILEA"
    # Intent Parser is fast/sync, but we can run it in threadpool if it gets heavy
    intent = await run_in_threadpool(parse_user_intent, user_input)
    
    if intent["action"] == "create_task":
        ctx = {
            "action": intent["action"],
            "data": intent["data"]
        }
        return templates.TemplateResponse(req, "ai_chat/shortcuts.html", ctx)

    # 2. Local AI - CRITICAL: Run in threadpool to prevent deadlock
    ai_response = await run_in_threadpool(ask_local_ai, user_input, tenant_id)
    
    ctx = {
        "user_message": user_input,
        "ai_message": ai_response
    }
    return templates.TemplateResponse(req, "ai_chat/message.html", ctx)


def _process_message_logic(req: Request | None, user_input: str, is_flask: bool) -> Any:
    if not user_input:
        if is_flask:
            return ""
        return HTMLResponse("")

    # Tenant context
    tenant_id = "KUKANILEA"
    if is_flask:
        tenant_id = getattr(g, "tenant_id", session.get("tenant_id", "KUKANILEA"))

    # 1. Intent / Shortcuts
    intent = parse_user_intent(user_input)
    if intent["action"] == "create_task":
        ctx = {
            "action": intent["action"],
            "data": intent["data"]
        }
        if is_flask:
            return render_template("ai_chat/shortcuts.html", **ctx)
        return templates.TemplateResponse(req, "ai_chat/shortcuts.html", ctx)

    # 2. Local AI
    ai_response = ask_local_ai(user_input, tenant_id=tenant_id)
    
    ctx = {
        "user_message": user_input,
        "ai_message": ai_response
    }
    
    if is_flask:
        return render_template("ai_chat/message.html", **ctx)
    return templates.TemplateResponse(req, "ai_chat/message.html", ctx)
