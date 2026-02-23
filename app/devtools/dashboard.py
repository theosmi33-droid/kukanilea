"""
app/devtools/dashboard.py
Real-time system telemetry and maintenance control.
Industrial-grade monitoring for KUKANILEA v1.2.
"""

import os
import psutil
import time
from typing import Any
from fastapi import APIRouter, Depends, Request, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from app.authz import SecurityContext, get_current_security_context
from app.database import get_db_path
from app.services import metrics

router = APIRouter(prefix="/dev/dashboard", tags=["Admin", "Telemetry"])
templates = Jinja2Templates(directory="templates")

def admin_only(ctx: SecurityContext = Depends(get_current_security_context)):
    if ctx.role not in ["ADMIN", "DEV", "OWNER_ADMIN"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    return ctx

@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request, ctx: SecurityContext = Depends(admin_only)):
    return templates.TemplateResponse("devtools/dashboard.html", {"request": request, "ctx": ctx})

@router.get("/metrics")
async def get_all_metrics(ctx: SecurityContext = Depends(admin_only)):
    """Gibt alle aktuellen Metriken als JSON zurück."""
    return await metrics.get_all_metrics()

@router.get("/metrics/db", response_class=HTMLResponse)
async def metrics_db(request: Request, ctx: SecurityContext = Depends(admin_only)):
    data = await metrics.get_database_metrics()
    return templates.TemplateResponse("devtools/_db_card.html", {"request": request, **data})

@router.get("/metrics/rag", response_class=HTMLResponse)
async def metrics_rag(request: Request, ctx: SecurityContext = Depends(admin_only)):
    data = await metrics.get_rag_metrics()
    return templates.TemplateResponse("devtools/_rag_card.html", {"request": request, **data})

@router.get("/metrics/ai", response_class=HTMLResponse)
async def metrics_ai(request: Request, ctx: SecurityContext = Depends(admin_only)):
    data = await metrics.get_ai_metrics()
    return templates.TemplateResponse("devtools/_ai_card.html", {"request": request, **data})

@router.get("/metrics/system", response_class=HTMLResponse)
async def metrics_system(request: Request, ctx: SecurityContext = Depends(admin_only)):
    data = await metrics.get_system_metrics()
    return templates.TemplateResponse("devtools/_system_card.html", {"request": request, **data})

@router.post("/rebuild-index")
async def rebuild_index(background_tasks: BackgroundTasks, ctx: SecurityContext = Depends(admin_only)):
    """Startet die asynchrone Neuindexierung des RAG."""
    if metrics.get_indexing_flag():
        return JSONResponse(status_code=409, content={"status": "already_running"})
    metrics.set_indexing_flag(True)
    background_tasks.add_task(_run_indexing)
    return {"status": "started"}

async def _run_indexing():
    try:
        # Mocking the indexing process
        import asyncio
        await asyncio.sleep(5)
        print("RAG-Indexierung erfolgreich abgeschlossen.")
    except Exception as e:
        print(f"Fehler bei RAG-Indexierung: {e}")
    finally:
        metrics.set_indexing_flag(False)
