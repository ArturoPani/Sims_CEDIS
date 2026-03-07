"""Utilidad para extraer el usuario actual de la sesión."""
from fastapi import HTTPException, Request


def get_current_user_id(request: Request) -> int:
    """Extrae user_id de la sesión. Lanza 401 si no hay sesión."""
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    return int(user_id)


def require_admin(request: Request) -> None:
    """Lanza 403 si el usuario actual no es admin."""
    if not request.session.get("is_admin"):
        raise HTTPException(status_code=403, detail="Solo el administrador puede realizar esta acción")
