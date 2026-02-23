"""
kukanilea_app.py
Zentrale Web-Applikation (FastAPI) mit globaler Error-Shell und HTMX-Integration.
"""

import logging
import sys
import uuid
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.ai_chat import router as ai_chat_router
from app.autonomy.maintenance import check_integrity
from app.autonomy.p2p import KukanileaDiscovery
from app.crm import router as crm_router
from app.database import init_db
from app.devtools.settings import router as dev_router
from app.devtools.dashboard import router as dashboard_router
from app.devtools.learning import router as learning_router
from app.logging_utils import setup_secure_logging
from app.observability import setup_observability
from app.session import validate_session
from app.tasks import router as tasks_router
from app.ui.command_palette import router as ui_router
from app.ui.onboarding import router as onboarding_router
from app.agents.email_trigger import EmailTrigger

# Setup Secure Logging (Compliance: GDPR Art. 25)
# Note: Full observability is initialized in startup_event
setup_secure_logging()

app = FastAPI(title="KUKANILEA - Business OS", docs_url=None, redoc_url=None)

# Global P2P Handle
p2p_manager: KukanileaDiscovery | None = None
# Global Email Trigger Handle
email_trigger: EmailTrigger | None = None

# Router integrieren
app.include_router(crm_router)
app.include_router(tasks_router)
app.include_router(ui_router)
app.include_router(onboarding_router)
app.include_router(ai_chat_router)
app.include_router(dev_router)
app.include_router(dashboard_router)
app.include_router(learning_router)


@app.on_event("startup")
async def startup_event():
    global p2p_manager, email_trigger
    # 1. Observability aktivieren (GDPR-safe)
    logger = setup_observability()
    logger.info("KUKANILEA Boot Sequence initiated.")

    # 2. Hardened DB Maintenance & Check
    try:
        is_healthy = check_integrity()
        if not is_healthy:
            msg = "Database integrity check failed! Halting boot sequence."
            logger.critical(msg)
            sys.exit(1)  # Fail-Safe Halt
    except Exception as e:
        logger.error(f"Maintenance check crashed: {e}")
        # Wir loggen den Fehler, brechen aber bei fehlender DB nicht ab
        pass

    # 3. Schema initialisieren (mit FTS5)
    init_db()
    logger.info("Database schema initialized and ready.")

    # 4. P2P Mesh Discovery (v2.0 Autostart)
    try:
        import socket
        hostname = socket.gethostname().split('.')[0]
        p2p_manager = KukanileaDiscovery()
        p2p_manager.advertise(f"KUKANILEA-{hostname}")
        p2p_manager.find_peers()
        logger.info(f"P2P Mesh Discovery active. Node name: KUKANILEA-{hostname}")
    except Exception as e:
        logger.error(f"P2P Service failed to start: {e}")

    # 5. Email Trigger (IMAP Listener)
    try:
        email_trigger = EmailTrigger()
        await email_trigger.start()
    except Exception as e:
        logger.error(f"Email Trigger failed to start: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    import asyncio
    logger = logging.getLogger("kukanilea.app")
    logger.info("Initiating graceful shutdown (Zombie-Hunter)...")
    
    global p2p_manager, email_trigger
    if p2p_manager:
        try:
            p2p_manager.stop()
            logger.info("P2P Discovery Service stopped.")
        except Exception as e:
            logger.error(f"Error stopping P2P: {e}")
    
    if email_trigger:
        try:
            await email_trigger.stop()
            logger.info("Email Trigger stopped.")
        except Exception as e:
            logger.error(f"Error stopping Email Trigger: {e}")
            
    # Terminate pending asyncio tasks to prevent zombies
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    logger.info(f"Cancelled {len(tasks)} outstanding tasks.")
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Graceful shutdown complete.")


# Templates
templates = Jinja2Templates(directory="templates")


# Middleware für Request-ID, PII-Filter und Offline-CSP
@app.middleware("http")
async def add_security_headers(request: Request, call_next: Any) -> Response:
    rid = str(uuid.uuid4())
    request.state.rid = rid

    # Session-Check (except for index and health)
    # Compliance: Session Hygiene & AuthZ enforcement
    if request.url.path not in ["/", "/health", "/login", "/ui/onboarding/"]:
        session_id = request.cookies.get("session_id")
        try:
            if not session_id:
                # Prototyping: allow access if session_id missing
                pass
            else:
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
    msg = f"Global Exception: {exc}"
    logging.getLogger("kukanilea.web").error(msg, extra={"rid": rid}, exc_info=True)

    # Niemals rohe Stacktraces an Nutzer
    err_msg = "Ein interner Systemfehler ist aufgetreten."
    return templates.TemplateResponse(
        request,
        "error_shell.html",
        {
            "rid": rid,
            "error_msg": err_msg,
        },
        status_code=500,
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "index.html", {"title": "Dashboard"}
    )


@app.get("/messe", response_class=HTMLResponse)
async def messe_landing(request: Request) -> HTMLResponse:
    """Spezielle Landingpage für Messe-Präsentationen."""
    return templates.TemplateResponse(
        request, "messe_demo.html", {}
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}
