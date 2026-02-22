from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.authz import SecurityContext, get_current_security_context

router = APIRouter(prefix="/ui/command", tags=["UX"])
templates = Jinja2Templates(directory="templates")


@router.get("/palette", response_class=HTMLResponse)
async def command_palette_ui(request: Request):
    """Returns the Command Palette HTMX component."""
    return templates.TemplateResponse(
        "components/command_palette.html", {"request": request}
    )


@router.post("/execute", response_class=HTMLResponse)
async def execute_command(
    request: Request, ctx: SecurityContext = Depends(get_current_security_context)
):
    """Executes a shortcut command from the palette."""
    form_data = await request.form()
    cmd = form_data.get("command", "").lower()

    # Simulation: Shortcut logic
    if "kunden" in cmd or "crm" in cmd:
        return HTMLResponse(
            "<div hx-get='/crm/' hx-trigger='load' hx-target='#main-content'>Navigiere zu CRM...</div>"
        )

    return HTMLResponse(f"<div class='text-red-500'>Unbekannter Befehl: {cmd}</div>")
