#!/usr/bin/env python3
"""
Entry point de la API del CEDIS.
Ejecutar con:  uvicorn api.main:app --reload
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv
import os

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")

# ── Rutas públicas (sin auth) ────────────────────────────────────
RUTAS_PUBLICAS = {"/login", "/health", "/docs", "/openapi.json", "/redoc"}


class AuthGuardMiddleware(BaseHTTPMiddleware):
    """Redirige a /login si no hay sesión activa, excepto rutas públicas."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Permitir siempre: rutas públicas y estáticos
        if path in RUTAS_PUBLICAS or path.startswith("/static/"):
            return await call_next(request)

        if not request.session.get("user"):
            accept = request.headers.get("accept", "")
            if "text/html" not in accept:
                return JSONResponse({"detail": "No autenticado"}, status_code=401)
            return RedirectResponse(url="/login", status_code=303)

        return await call_next(request)


app = FastAPI(
    title="CEDIS Sim API",
    description="API para gestionar robots, pedidos y simulación del CEDIS.",
    version="0.1.0",
)

# Orden: AuthGuard (added 1st = innermost) → SessionMiddleware (added 2nd = outermost)
# Ejecución: Request → SessionMiddleware → AuthGuard → app
app.add_middleware(AuthGuardMiddleware)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=3600 * 8)

# ── Routers ──────────────────────────────────────────────────────
from api.routers import robots, pedidos, simulacion, layout
from api.routers.metricas_router import router as metricas_router
from api.routers.auth import router as auth_router
from api.routers.experimento import router as experimento_router
app.include_router(auth_router)
app.include_router(robots.router)
app.include_router(pedidos.router)
app.include_router(simulacion.router)

# ── Crear tablas al iniciar (idempotente) ────────────────────────
from db.connection import init_schema
try:
    init_schema()
except Exception:
    pass  # la BD puede no estar disponible en dev local
app.include_router(layout.router)
app.include_router(metricas_router)
app.include_router(experimento_router)

# ── Servir frontend estático ─────────────────────────────────────
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="frontend")

# ── Páginas ──────────────────────────────────────────────────────
@app.get("/login")
def login_page():
    """Sirve la página de login."""
    path = os.path.join(FRONTEND_DIR, "login.html")
    if os.path.isfile(path):
        return FileResponse(path)
    return {"error": "login.html not found"}


@app.get("/admin")
def admin_page(request: Request):
    """Sirve la página de administración (solo admin)."""
    if not request.session.get("is_admin"):
        return RedirectResponse(url="/", status_code=303)
    path = os.path.join(FRONTEND_DIR, "admin.html")
    if os.path.isfile(path):
        return FileResponse(path)
    return {"error": "admin.html not found"}


@app.get("/")
def root():
    """Sirve el frontend (index.html)."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    return {"servicio": "CEDIS Sim API", "version": "0.1.0", "estado": "activo"}

@app.get("/metricas-page")
def metricas_page():
    """Sirve la página de comparación de métricas."""
    path = os.path.join(FRONTEND_DIR, "metricas.html")
    if os.path.isfile(path):
        return FileResponse(path)
    raise Exception("metricas.html not found")

@app.get("/experimento-page")
def experimento_page():
    """Sirve la página de experimento rápido."""
    path = os.path.join(FRONTEND_DIR, "experimento.html")
    if os.path.isfile(path):
        return FileResponse(path)
    raise Exception("experimento.html not found")

@app.get("/health")
def health():
    return {"status": "ok"}
