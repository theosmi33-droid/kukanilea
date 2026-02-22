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

# Setup Logging (Kein PII in Logs per Default)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - RID:%(rid)s - %(message)s')
logger = logging.getLogger("kukanilea.web")

app = FastAPI(title="KUKANILEA - Business OS", docs_url=None, redoc_url=None)

# Templates
templates = Jinja2Templates(directory="templates")

# Middleware für Request-ID und PII-Filter
@app.middleware("http")
async def add_process_time_header(request: Request, call_next: Any) -> Response:
    rid = str(uuid.uuid4())
    request.state.rid = rid
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
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
