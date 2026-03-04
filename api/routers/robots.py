"""
Router de robots — alta, listado y baja de robots en la BD.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from db import crud

router = APIRouter(prefix="/robots", tags=["Robots"])


# ── Schemas de entrada / salida ──────────────────────────────────

class RobotIn(BaseModel):
    nombre: str
    escenario: str
    spawn_x: int
    spawn_y: int


class RobotOut(BaseModel):
    robot_id: int
    nombre: str
    escenario: str
    spawn_x: int
    spawn_y: int
    activo: bool


# ── Endpoints ────────────────────────────────────────────────────

@router.get("", response_model=list[RobotOut])
def listar_robots(
    escenario: str = Query(..., description="Nombre del escenario"),
    solo_activos: bool = Query(True, description="Filtrar solo robots activos"),
):
    """Lista los robots registrados para un escenario."""
    return crud.listar_robots(escenario, solo_activos=solo_activos)


@router.post("", response_model=RobotOut, status_code=201)
def crear_robot(robot: RobotIn):
    """Da de alta un nuevo robot con su punto de spawn."""
    robot_id = crud.insertar_robot(
        nombre=robot.nombre,
        escenario=robot.escenario,
        spawn_x=robot.spawn_x,
        spawn_y=robot.spawn_y,
    )
    return {
        "robot_id": robot_id,
        "nombre": robot.nombre,
        "escenario": robot.escenario,
        "spawn_x": robot.spawn_x,
        "spawn_y": robot.spawn_y,
        "activo": True,
    }


@router.delete("/{robot_id}", status_code=200)
def desactivar_robot(robot_id: int):
    """Desactiva (baja lógica) un robot."""
    eliminado = crud.desactivar_robot(robot_id)
    if not eliminado:
        raise HTTPException(status_code=404, detail=f"Robot {robot_id} no encontrado.")
    return {"mensaje": f"Robot {robot_id} desactivado."}
