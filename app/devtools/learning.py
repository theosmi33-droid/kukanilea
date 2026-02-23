from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc

from app.authz import SecurityContext, get_current_security_context
from app.models.rule import get_sa_session, RuleProposal
from app.core.self_learning import apply_approved_rule_to_playbook, propose_rule

router = APIRouter(prefix="/dev/rules", tags=["Admin", "Learning"])
templates = Jinja2Templates(directory="templates")

def admin_only(ctx: SecurityContext = Depends(get_current_security_context)):
    if ctx.role not in ["ADMIN", "DEV", "OWNER_ADMIN"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    return ctx

@router.get("/proposals", response_class=HTMLResponse)
async def list_proposals(request: Request, ctx: SecurityContext = Depends(admin_only)):
    """Zeigt alle ausstehenden Regelentwürfe an."""
    session = get_sa_session()
    proposals = session.query(RuleProposal).filter_by(status='pending').order_by(desc(RuleProposal.created_at)).all()
    session.close()
    
    return templates.TemplateResponse("devtools/rule_proposals.html", {
        "request": request, 
        "proposals": proposals, 
        "ctx": ctx
    })

@router.post("/proposals/{proposal_id}/approve", response_class=HTMLResponse)
async def approve_proposal(request: Request, proposal_id: int, ctx: SecurityContext = Depends(admin_only)):
    """Setzt den Status auf 'approved' und hängt den Regeltext an die PLAYBOOK.md an."""
    success = apply_approved_rule_to_playbook(proposal_id)
    
    # HTMX Response: Update der Liste
    session = get_sa_session()
    proposals = session.query(RuleProposal).filter_by(status='pending').order_by(desc(RuleProposal.created_at)).all()
    session.close()
    
    return templates.TemplateResponse("devtools/_rule_list.html", {
        "request": request, 
        "proposals": proposals
    })

@router.post("/proposals/{proposal_id}/reject", response_class=HTMLResponse)
async def reject_proposal(request: Request, proposal_id: int, ctx: SecurityContext = Depends(admin_only)):
    """Setzt den Status auf 'rejected'."""
    session = get_sa_session()
    proposal = session.query(RuleProposal).filter_by(id=proposal_id, status='pending').first()
    if proposal:
        proposal.status = 'rejected'
        import datetime
        proposal.reviewed_at = datetime.datetime.utcnow()
        session.commit()
    
    proposals = session.query(RuleProposal).filter_by(status='pending').order_by(desc(RuleProposal.created_at)).all()
    session.close()
    
    return templates.TemplateResponse("devtools/_rule_list.html", {
        "request": request, 
        "proposals": proposals
    })

@router.post("/trigger", response_class=JSONResponse)
async def trigger_propose(ctx: SecurityContext = Depends(admin_only)):
    """Stößt die asynchrone Regelerstellung manuell an."""
    proposal_id = await propose_rule()
    return {"status": "success", "proposal_id": proposal_id}
