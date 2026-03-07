"""
Router de simulación — iniciar, detener, consultar estado y métricas.
"""
import json
import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from api.sim_runner import runner
from sim_core import Pedido, SimConfig
from db import crud
from api.deps import get_current_user_id

# ── Configuración de features por escenario ────────────────────
CONFIG_ESCENARIOS: dict[str, SimConfig] = {
    "benchmark":        SimConfig(usar_bateria=False),          # lógica original
    "pasillosDirigidos": SimConfig(usar_bateria=True),           # batería + relevos
}

def _config_para(escenario: str) -> SimConfig:
    """Devuelve la SimConfig del escenario, o defaults (benchmark) si no existe."""
    return CONFIG_ESCENARIOS.get(escenario, SimConfig())

router = APIRouter(prefix="/simulacion", tags=["Simulación"])


# ── Schemas ──────────────────────────────────────────────────────

class IniciarSimIn(BaseModel):
    escenario: str = "benchmark"
    seed: int = 42
    ticks: int = 10000
    seg_por_tick: float = 0.05


# ── Helpers ──────────────────────────────────────────────────────

def _cargar_politica_transito(escenario: str):
    """
    Carga politica_transito.json del escenario y convierte las claves
    de strings JSON a tuplas que espera sim_core / a_estrella.
    Devuelve (movimientos_permitidos, costos_direccion, celdas_no_stop)
    o (None, None, None) si el archivo no existe.
    """
    ruta = os.path.join("outputs", escenario, "politica_transito.json")
    if not os.path.isfile(ruta):
        return None, None, None

    with open(ruta, "r", encoding="utf-8") as f:
        data = json.load(f)

    # movimientos: "x,y" -> [(dx,dy), ...]  →  (x,y) -> [(dx,dy), ...]
    raw_mov = data.get("movimientos", {})
    movimientos = {}
    for key_str, dirs in raw_mov.items():
        parts = key_str.split(",")
        celda = (int(parts[0]), int(parts[1]))
        movimientos[celda] = [tuple(d) for d in dirs]

    # costos_direccion: "x,y,dx,dy" -> float  →  (x,y,dx,dy) -> float
    raw_cos = data.get("costos_direccion", {})
    costos = {}
    for key_str, costo in raw_cos.items():
        parts = key_str.split(",")
        costos[(int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))] = float(costo)

    # no_stop: ["x,y", ...]  →  {(x,y), ...}
    raw_ns = data.get("no_stop", [])
    no_stop = set()
    for key_str in raw_ns:
        parts = key_str.split(",")
        no_stop.add((int(parts[0]), int(parts[1])))

    return (
        movimientos if movimientos else None,
        costos if costos else None,
        no_stop if no_stop else None,
    )


# ── Endpoints ────────────────────────────────────────────────────

@router.post("/iniciar", status_code=200)
def iniciar_simulacion(params: IniciarSimIn, request: Request):
    """
    Inicia la simulación en un hilo de fondo.
    Usa los robots activos y pedidos del escenario almacenados en la BD.
    """
    uid = get_current_user_id(request)

    # Obtener spawns de robots activos en BD (del usuario)
    robots_db = crud.listar_robots(params.escenario, solo_activos=True, user_id=uid)
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
        movimientos, costos, no_stop = _cargar_politica_transito(params.escenario)
        cfg = _config_para(params.escenario)
        runner.iniciar(
            escenario=params.escenario,
            seed=params.seed,
            ticks=params.ticks,
            pedidos=pedidos,
            puntos_spawn=puntos_spawn,
            num_robots=num_robots,
            seg_por_tick=params.seg_por_tick,
            movimientos_permitidos=movimientos,
            costos_direccion=costos,
            celdas_no_stop=no_stop,
            config=cfg,
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
    request: Request,
    guardar: bool = Query(False, description="Si es True, guarda las métricas en la BD (tabla runs)."),
    nombre: str = Query(None, description="Nombre personalizado para identificar la corrida."),
):
    """Devuelve métricas parciales o finales de la simulación."""
    m = runner.metricas()
    if m is None:
        raise HTTPException(status_code=400, detail="No hay simulación (activa o finalizada).")

    if guardar:
        uid = get_current_user_id(request)
        etiqueta = nombre.strip() if nombre else runner.escenario
        run_id = crud.guardar_run(etiqueta, m, user_id=uid)
        m["run_id"] = run_id
        m["guardado_en_bd"] = True

    return m
