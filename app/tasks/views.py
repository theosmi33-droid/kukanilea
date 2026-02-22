from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.authz import SecurityContext, get_current_security_context, require_role

router = APIRouter(prefix="/tasks", tags=["Tasks"])
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
@require_role(["ADMIN", "OPERATOR", "USER"])
async def tasks_board(
    request: Request,
    ctx: SecurityContext = Depends(get_current_security_context)
):
    """Displays Kanban board for the current tenant."""
    # Simulation: Task list restricted by tenant_id
    tasks = [
        {"id": 101, "title": "Abnahme SHK Müller", "status": "todo"},
        {"id": 102, "title": "Materialbestellung Bedachung", "status": "inprogress"},
        {"id": 103, "title": "Bericht Facility Ops", "status": "done"}
    ]
    return templates.TemplateResponse(
        "tasks/board.html",
        {"request": request, "tasks": tasks, "tenant_id": ctx.tenant_id}
    )
