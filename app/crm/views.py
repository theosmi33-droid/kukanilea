from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.authz import SecurityContext, get_current_security_context, require_role

router = APIRouter(prefix="/crm", tags=["CRM"])
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
@require_role(["ADMIN", "OPERATOR"])
async def crm_list(
    request: Request, ctx: SecurityContext = Depends(get_current_security_context)
):
    """Lists customers for the current tenant."""
    # Simulation: Database query restricted by tenant_id
    customers = [
        {"id": 1, "name": "Müller Bedachungen", "city": "Berlin"},
        {"id": 2, "name": "SHK Schulze", "city": "Potsdam"},
    ]
    return templates.TemplateResponse(
        "crm/list.html",
        {"request": request, "customers": customers, "tenant_id": ctx.tenant_id},
    )
