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
from app.ai.voice_parser import voice_parser
from app.ai.vision_parser import vision_parser
from app.agents.orchestrator_v2 import delegate_task, wrap_with_salt

router = APIRouter(prefix="/ai-chat", tags=["AI", "Chat"])
templates = Jinja2Templates(directory="templates")

@router.post("/vision-analyze", response_class=JSONResponse)
async def analyze_site_image(request: Request, file: UploadFile = File(...)) -> Any:
    """Endpunkt für mobile Bildanalyse. Analysiert Fotos lokal und triggert Reparaturplanung."""
    # 1. Temporär speichern
    temp_dir = "instance/vision_temp"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"vision_{secrets.token_hex(4)}_{file.filename}")
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # 2. Lokale Bildanalyse (Moondream)
        description = await run_in_threadpool(vision_parser.analyze_image, temp_path)
        
        if not description or "Fehler" in description:
            return JSONResponse({"status": "error", "message": "Bild konnte nicht analysiert werden."}, status_code=400)

        # 3. Vorprüfung durch Observer (Analog zu Voice Command)
        from app.agents.observer import ObserverAgent
        observer = ObserverAgent()
        # Wir nutzen 'voice_command' Action-Typ auch für Vision-Text Validierung
        allowed, reason = observer.validate_action("voice_command", {"text": description})
        
        if not allowed:
            return {
                "status": "draft",
                "description": description,
                "agent_response": f"Bildanalyse als Entwurf markiert: {reason}",
                "is_draft": True
            }

        # 4. Delegation an Orchestrator V2 (SST Härtung)
        salted_vision_text = wrap_with_salt(f"BILDANALYSE VOR-ORT: {description}")
        
        agent_response = await delegate_task(salted_vision_text, tenant_id="MOBILE_VISION", user_id="meister_kamera")
        
        # 5. Sicherheit: Falls Orchestrator/Observer Veto einlegt
        is_draft = "Sicherheitsblockade" in agent_response or "Human-in-the-loop" in agent_response
        
        return {
            "status": "ok",
            "description": description,
            "agent_response": agent_response,
            "is_draft": is_draft
        }
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
    finally:
        # 6. Sicherheit: Sofortige Löschroutine für DSGVO (Schritt 6)
        if os.path.exists(temp_path):
            os.remove(temp_path)

@router.post("/transcribe", response_class=JSONResponse)
async def transcribe_audio(request: Request, file: UploadFile = File(...)) -> Any:
    """Endpunkt für mobile Sprachsteuerung. Transkribiert Audio lokal und triggert Agenten."""
    # 1. Temporär speichern
    temp_dir = "instance/voice_temp"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"voice_{secrets.token_hex(4)}_{file.filename}")
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # 2. Lokale Transkription (im Threadpool da CPU-lastig)
        text = await run_in_threadpool(voice_parser.transcribe, temp_path)
        
        if not text:
            return JSONResponse({"status": "error", "message": "Sprache konnte nicht erkannt werden."}, status_code=400)

        # 3. Vorprüfung durch Observer (Schritt 6)
        from app.agents.observer import ObserverAgent
        observer = ObserverAgent()
        allowed, reason = observer.validate_action("voice_command", {"text": text})
        
        if not allowed:
            # Als Entwurf markieren und Rückmeldung geben
            return {
                "status": "draft",
                "transcription": text,
                "agent_response": f"Befehl als Entwurf markiert: {reason}",
                "is_draft": True
            }

        # 4. Delegation an Orchestrator V2 (SST wird intern in delegate_task/call_tool gehandhabt)
        # Wir wickeln den Input hier zusätzlich in SST ein, um den "Voice Channel" zu markieren.
        from app.agents.orchestrator_v2 import wrap_with_salt
        # Hier nutzen wir das globale Salt des Orchestrators oder ein temporäres
        salted_voice_text = wrap_with_salt(text)
        
        agent_response = await delegate_task(salted_voice_text, tenant_id="MOBILE_VOICE", user_id="meister_baustelle")
        
        # 5. Sicherheit: Falls Orchestrator/Observer Veto einlegt
        is_draft = "Sicherheitsblockade" in agent_response or "Human-in-the-loop" in agent_response
        
        return {
            "status": "ok",
            "transcription": text,
            "agent_response": agent_response,
            "is_draft": is_draft
        }
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

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
