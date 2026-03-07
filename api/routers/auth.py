"""
Router de autenticación – login / logout con sesión cookie.
El admin se autentica con credenciales de .env; los demás usuarios contra la BD.
"""
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from dotenv import load_dotenv
import os
from db import crud
from api.deps import get_current_user_id, require_admin

load_dotenv()

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

router = APIRouter(tags=["auth"])


@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    """Valida credenciales: primero admin (.env), luego BD."""
    # Admin hardcoded
    if username == ADMIN_USER and password == ADMIN_PASSWORD:
        request.session["user"] = username
        request.session["user_id"] = 0  # admin virtual
        request.session["is_admin"] = True
        return RedirectResponse(url="/", status_code=303)

    # Usuario normal de BD
    user = crud.autenticar_usuario(username, password)
    if user:
        request.session["user"] = user["username"]
        request.session["user_id"] = user["user_id"]
        request.session["is_admin"] = False
        return RedirectResponse(url="/", status_code=303)

    return RedirectResponse(url="/login?error=1", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    """Cierra sesión."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@router.get("/me")
async def me(request: Request):
    """Devuelve info del usuario actual."""
    user = request.session.get("user")
    user_id = request.session.get("user_id")
    is_admin = request.session.get("is_admin", False)
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")
    return {"username": user, "user_id": user_id, "is_admin": is_admin}


# ── Endpoints de admin ─────────────────────────────────────────────

@router.post("/admin/usuarios")
async def crear_usuario_admin(request: Request, username: str = Form(...), password: str = Form(...)):
    """Solo admin: crea un usuario nuevo."""
    require_admin(request)
    if not username.strip() or len(password) < 4:
        return JSONResponse({"error": "El usuario no puede estar vacío y la contraseña debe tener al menos 4 caracteres."}, status_code=400)
    existing = crud.buscar_usuario(username.strip())
    if existing:
        return JSONResponse({"error": f"El usuario '{username.strip()}' ya existe."}, status_code=409)
    user_id = crud.crear_usuario(username.strip(), password)
    return {"ok": True, "user_id": user_id, "username": username.strip()}


@router.get("/admin/usuarios")
async def listar_usuarios_admin(request: Request):
    """Solo admin: lista todos los usuarios."""
    require_admin(request)
    return crud.listar_usuarios()
