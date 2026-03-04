"""
Router de simulación — iniciar, detener, consultar estado y métricas.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from api.sim_runner import runner
from sim_core import Pedido
from db import crud

router = APIRouter(prefix="/simulacion", tags=["Simulación"])


# ── Schemas ──────────────────────────────────────────────────────

class IniciarSimIn(BaseModel):
    escenario: str = "benchmark"
    seed: int = 42
    ticks: int = 10000
    seg_por_tick: float = 0.05


# ── Endpoints ────────────────────────────────────────────────────

@router.post("/iniciar", status_code=200)
def iniciar_simulacion(params: IniciarSimIn):
    """
    Inicia la simulación en un hilo de fondo.
    Usa los robots activos y pedidos del escenario almacenados en la BD.
    """
    # Obtener spawns de robots activos en BD
    robots_db = crud.listar_robots(params.escenario, solo_activos=True)
    if not robots_db:
        raise HTTPException(
            status_code=400,
            detail=f"No hay robots activos en el escenario '{params.escenario}'. "
                   f"Registra robots primero con POST /robots.",
        )
    puntos_spawn = [(r["spawn_x"], r["spawn_y"]) for r in robots_db]
    num_robots = len(robots_db)

    # Obtener pedidos de BD
    pedidos_db = crud.listar_pedidos(params.escenario, seed=params.seed)
    if not pedidos_db:
        raise HTTPException(
            status_code=400,
            detail=f"No hay pedidos para escenario='{params.escenario}' seed={params.seed}. "
                   f"Genera pedidos primero con POST /pedidos/generar.",
        )

    pedidos = [
        Pedido(
            pedido_id=p["pedido_id"],
            anaquel_id=p["anaquel_id"],
            estacion_id=p["estacion_id"],
            tick_creacion=p["tick_creacion"],
        )
        for p in pedidos_db
    ]

    try:
        runner.iniciar(
            escenario=params.escenario,
            seed=params.seed,
            ticks=params.ticks,
            pedidos=pedidos,
            puntos_spawn=puntos_spawn,
            num_robots=num_robots,
            seg_por_tick=params.seg_por_tick,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {
        "mensaje": "Simulación iniciada.",
        "escenario": params.escenario,
        "robots": num_robots,
        "pedidos": len(pedidos),
        "ticks": params.ticks,
    }


@router.post("/detener", status_code=200)
def detener_simulacion():
    """Detiene la simulación en curso."""
    if not runner.activo and not runner.finalizado:
        raise HTTPException(status_code=400, detail="No hay simulación en curso.")
    runner.detener()
    return {"mensaje": "Simulación detenida."}


@router.get("/estado")
def obtener_estado():
    """
    Endpoint de polling — devuelve tick actual, estado de cada robot
    (posición, estado, ETA) y estado de cada pedido.
    """
    return runner.estado()


@router.get("/metricas")
def obtener_metricas(
    guardar: bool = Query(False, description="Si es True, guarda las métricas en la BD (tabla runs)."),
    nombre: str = Query(None, description="Nombre personalizado para identificar la corrida."),
):
    """Devuelve métricas parciales o finales de la simulación."""
    m = runner.metricas()
    if m is None:
        raise HTTPException(status_code=400, detail="No hay simulación (activa o finalizada).")

    if guardar:
        etiqueta = nombre.strip() if nombre else runner.escenario
        run_id = crud.guardar_run(etiqueta, m)
        m["run_id"] = run_id
        m["guardado_en_bd"] = True

    return m
