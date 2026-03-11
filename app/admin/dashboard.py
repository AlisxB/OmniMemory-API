"""
Router do Admin Dashboard — serve o HTML e redireciona rotas.
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse
from pathlib import Path

router = APIRouter(tags=["admin — dashboard"])

DASHBOARD_FILE = Path(__file__).parent.parent / "static" / "dashboard.html"


@router.get("/", include_in_schema=False)
async def admin_root():
    """Redirect / → /admin/dashboard."""
    return RedirectResponse(url="/admin/dashboard")


@router.get("/dashboard", include_in_schema=False)
async def serve_dashboard():
    """Serve o Admin Dashboard (autenticação via JWT no client-side)."""
    if not DASHBOARD_FILE.exists():
        return HTMLResponse("<h1>Dashboard não encontrado.</h1>", status_code=404)
    return HTMLResponse(content=DASHBOARD_FILE.read_text(encoding="utf-8"))


@router.get("/login", include_in_schema=False)
async def serve_login():
    """Redirect para o dashboard (login está embutido nele)."""
    return RedirectResponse(url="/admin/dashboard")
