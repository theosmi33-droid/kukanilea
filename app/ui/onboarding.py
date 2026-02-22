"""
app/ui/onboarding.py
HTMX-basierter Onboarding Wizard für die 110% KUKANILEA Vision.
"""

import logging

import anyio
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from app.authz import SecurityContext, get_current_security_context
from app.seeder import apply_vertical_kit

router = APIRouter(prefix="/ui/onboarding", tags=["UX", "Onboarding"])
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger("kukanilea.onboarding")


@router.get("/", response_class=HTMLResponse)
async def onboarding_wizard(request: Request):
    """Rendert den Setup-Wizard beim ersten Start."""
    return templates.TemplateResponse("onboarding/wizard.html", {"request": request})


@router.post("/setup")
async def setup_vertical(
    request: Request,
    vertical: str = Form(...),
    ctx: SecurityContext = Depends(get_current_security_context),
):
    """
    Injiziert branchenspezifische Vorlagen via Thread-Pool Offloading.
    Verhindert Event-Loop Blocking während des Stress-Tests.
    """
    logger.info(f"User {ctx.user_id} applying Vertical Kit: {vertical}")

    # AUTO-REMEDIATION: Run sync DB operation in thread
    success = await anyio.to_thread.run_sync(
        apply_vertical_kit, ctx.tenant_id, vertical
    )

    if success:
        logger.info(f"Successfully seeded vertical '{vertical}'.")
    else:
        logger.error(f"Failed to seed vertical '{vertical}'.")

    # HTMX Redirect-Header, um den Client auf das Dashboard zu leiten
    response = Response(status_code=204)
    response.headers["HX-Redirect"] = "/crm/"
    return response
