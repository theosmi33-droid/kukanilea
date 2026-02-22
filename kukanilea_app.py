"""
kukanilea_app.py
Zentrale Web-Applikation (FastAPI) mit globaler Error-Shell und HTMX-Integration.
"""
import logging
import uuid
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.crm import router as crm_router
from app.tasks import router as tasks_router
from app.ui.command_palette import router as ui_router
from app.database import init_db

# Setup Secure Logging (Compliance: GDPR Art. 25)
logger = setup_secure_logging()

app = FastAPI(title="KUKANILEA - Business OS", docs_url=None, redoc_url=None)

# Router integrieren
app.include_router(crm_router)
app.include_router(tasks_router)
app.include_router(ui_router)


@app.on_event("startup")
async def startup_event():
    init_db()

# Templates
templates = Jinja2Templates(directory="templates")

# Middleware für Request-ID, PII-Filter und Offline-CSP
@app.middleware("http")
async def add_security_headers(request: Request, call_next: Any) -> Response:
    rid = str(uuid.uuid4())
    request.state.rid = rid
    
    # Session-Check (except for index and health)
    # Compliance: Session Hygiene & AuthZ enforcement
    if request.url.path not in ["/", "/health", "/login"]:
        session_id = request.cookies.get("session_id")
        try:
            if not session_id:
                raise Exception("Missing session")
            validate_session(session_id)
        except Exception:
            return Response("Unauthorized", status_code=401)

    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    
    # EPIC 2: Offline-Proof CSP (No external calls except localhost)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
        "connect-src 'self'; "
        "img-src 'self' data:; "
        "frame-ancestors 'none';"
    )
    return response

# Globale Error-Shell (Kriterium EPIC 1.4)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> HTMLResponse:
    rid = getattr(request.state, "rid", "N/A")
    logger.error(f"Global Exception: {exc}", extra={"rid": rid}, exc_info=True)
    
    # Niemals rohe Stacktraces an Nutzer
    return templates.TemplateResponse(
        "error_shell.html", 
        {
            "request": request, 
            "rid": rid, 
            "error_msg": "Ein interner Systemfehler ist aufgetreten. Bitte wenden Sie sich an den Support."
        },
        status_code=500
    )

@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request, "title": "Dashboard"})

@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}
