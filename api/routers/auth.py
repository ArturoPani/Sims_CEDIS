"""
Router de autenticación – login / logout con sesión cookie.
Credenciales guardadas en .env (ADMIN_USER, ADMIN_PASSWORD).
"""
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
import os

load_dotenv()

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

router = APIRouter(tags=["auth"])


@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    """Valida credenciales y crea la sesión."""
    if username == ADMIN_USER and password == ADMIN_PASSWORD:
        request.session["user"] = username
        return RedirectResponse(url="/", status_code=303)
    # Redirigir al login con mensaje de error
    return RedirectResponse(url="/login?error=1", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    """Cierra sesión."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
