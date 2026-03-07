"""
Router de robots — alta, listado y baja de robots en la BD.
"""
import json
import os
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional
from db import crud
from api.deps import get_current_user_id

router = APIRouter(prefix="/robots", tags=["Robots"])


# ── Schemas de entrada / salida ──────────────────────────────────

class RobotIn(BaseModel):
    nombre: str
    escenario: str
    spawn_x: Optional[int] = None
    spawn_y: Optional[int] = None


class RobotOut(BaseModel):
    robot_id: int
    nombre: str
    escenario: str
    spawn_x: int
    spawn_y: int
    activo: bool


# ── Helpers ──────────────────────────────────────────────────────

def _siguiente_spawn(escenario: str, user_id: int) -> tuple[int, int]:
    """Devuelve el siguiente punto de spawn libre para el escenario."""
    ruta = os.path.join("outputs", escenario, "spawn.json")
    if not os.path.isfile(ruta):
        raise HTTPException(status_code=404, detail=f"spawn.json no encontrado para '{escenario}'.")
    with open(ruta, "r", encoding="utf-8") as f:
        todos_spawns = json.load(f)  # [[x,y], ...]

    # Obtener spawns ya ocupados por robots activos del usuario
    robots_activos = crud.listar_robots(escenario, solo_activos=True, user_id=user_id)
    ocupados = {(r["spawn_x"], r["spawn_y"]) for r in robots_activos}

    for sp in todos_spawns:
        pos = (int(sp[0]), int(sp[1]))
        if pos not in ocupados:
            return pos

    raise HTTPException(
        status_code=409,
        detail=f"No hay puntos de spawn disponibles en '{escenario}'. "
               f"({len(ocupados)}/{len(todos_spawns)} ocupados).",
    )


# ── Endpoints ────────────────────────────────────────────────────

@router.get("", response_model=list[RobotOut])
def listar_robots(
    request: Request,
    escenario: str = Query(..., description="Nombre del escenario"),
    solo_activos: bool = Query(True, description="Filtrar solo robots activos"),
):
    """Lista los robots registrados para un escenario del usuario actual."""
    uid = get_current_user_id(request)
    return crud.listar_robots(escenario, solo_activos=solo_activos, user_id=uid)


@router.get("/next-spawn")
def siguiente_spawn(request: Request, escenario: str = Query("benchmark")):
    """Devuelve el siguiente punto de spawn disponible."""
    uid = get_current_user_id(request)
    x, y = _siguiente_spawn(escenario, uid)
    return {"spawn_x": x, "spawn_y": y}


@router.post("", response_model=RobotOut, status_code=201)
def crear_robot(robot: RobotIn, request: Request):
    """Da de alta un nuevo robot. Si no se envía spawn_x/y, se asigna automáticamente."""
    uid = get_current_user_id(request)
    sx, sy = robot.spawn_x, robot.spawn_y
    if sx is None or sy is None:
        sx, sy = _siguiente_spawn(robot.escenario, uid)

    robot_id = crud.insertar_robot(
        nombre=robot.nombre,
        escenario=robot.escenario,
        spawn_x=sx,
        spawn_y=sy,
        user_id=uid,
    )
    return {
        "robot_id": robot_id,
        "nombre": robot.nombre,
        "escenario": robot.escenario,
        "spawn_x": sx,
        "spawn_y": sy,
        "activo": True,
    }


@router.delete("/{robot_id}", status_code=200)
def desactivar_robot(robot_id: int, request: Request):
    """Desactiva (baja lógica) un robot del usuario actual."""
    uid = get_current_user_id(request)
    eliminado = crud.desactivar_robot(robot_id, user_id=uid)
    if not eliminado:
        raise HTTPException(status_code=404, detail=f"Robot {robot_id} no encontrado.")
    return {"mensaje": f"Robot {robot_id} desactivado."}
