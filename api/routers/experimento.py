"""
Router de experimento rápido — corre una simulación completa sin tocar la BD,
genera pedidos en memoria y devuelve métricas al terminar.
Opcionalmente guarda la corrida en la tabla `runs`.
"""
import json
import os
from typing import Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from sim_core import Pedido, SimAlmacen, SimConfig, cargar_layout
from api.routers.simulacion import _cargar_politica_transito, CONFIG_ESCENARIOS
from db import crud
from api.deps import get_current_user_id

router = APIRouter(prefix="/experimento", tags=["Experimento rápido"])


# ── Schemas ──────────────────────────────────────────────────────

class ExperimentoIn(BaseModel):
    escenario: str = "benchmark"
    num_robots: int = Field(5, ge=1, le=500)
    seed: int = 42
    num_pedidos: int = Field(300, ge=1, le=5000)
    ticks: int = Field(10000, ge=100, le=100000)
    burst: bool = False
    guardar: bool = False
    nombre: Optional[str] = None


# ── Helpers ──────────────────────────────────────────────────────

def _generar_pedidos_memoria(
    escenario: str,
    num_pedidos: int,
    seed: int,
    burst: bool,
) -> list[Pedido]:
    """Genera pedidos al vuelo (misma lógica que generador_pedidos.py)."""
    ruta_est = os.path.join("outputs", escenario, "estaciones.json")
    ruta_anaq = os.path.join("outputs", escenario, "anaqueles.json")

    if not os.path.isfile(ruta_est) or not os.path.isfile(ruta_anaq):
        raise FileNotFoundError(
            f"No se encontraron estaciones/anaqueles para escenario '{escenario}'."
        )

    with open(ruta_est, "r", encoding="utf-8") as f:
        estaciones = json.load(f)
    with open(ruta_anaq, "r", encoding="utf-8") as f:
        anaqueles = json.load(f)

    ids_estacion = [e["estacion_id"] for e in estaciones]
    ids_anaquel = [a["anaquel_id"] for a in anaqueles]

    rng = np.random.default_rng(seed)
    pedidos: list[Pedido] = []

    for i in range(num_pedidos):
        estacion_id = int(rng.choice(ids_estacion))
        anaquel_id = int(rng.choice(ids_anaquel))

        if burst:
            if rng.random() < 0.70:
                tick_creacion = int(rng.integers(0, 2001))
            else:
                tick_creacion = int(rng.integers(0, 10001))
        else:
            tick_creacion = 0

        pedidos.append(
            Pedido(
                pedido_id=i,
                anaquel_id=anaquel_id,
                estacion_id=estacion_id,
                tick_creacion=tick_creacion,
            )
        )

    return pedidos


def _cargar_spawns(escenario: str, num_robots: int) -> list[tuple]:
    """Lee spawn.json y devuelve los primeros N puntos (clampea si hay menos)."""
    ruta = os.path.join("outputs", escenario, "spawn.json")
    if not os.path.isfile(ruta):
        raise FileNotFoundError(f"No existe spawn.json para escenario '{escenario}'.")

    with open(ruta, "r", encoding="utf-8") as f:
        todos = json.load(f)

    n = min(num_robots, len(todos))
    return [(int(p[0]), int(p[1])) for p in todos[:n]]


# ── Endpoint ─────────────────────────────────────────────────────

@router.post("/correr")
def correr_experimento(params: ExperimentoIn, request: Request):
    """
    Corre una simulación completa de forma síncrona (sin hilo de fondo)
    y devuelve las métricas al terminar.
    NO requiere robots ni pedidos en la BD.
    """
    # Validar escenario
    carpeta = os.path.join("outputs", params.escenario)
    if not os.path.isdir(carpeta):
        raise HTTPException(status_code=404, detail=f"Escenario '{params.escenario}' no encontrado.")

    try:
        spawns = _cargar_spawns(params.escenario, params.num_robots)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        pedidos = _generar_pedidos_memoria(
            params.escenario, params.num_pedidos, params.seed, params.burst,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Cargar layout
    grid, estacion_dock, anaquel_home, _ = cargar_layout(
        os.path.join(carpeta, "layout.npy"),
        os.path.join(carpeta, "estaciones.json"),
        os.path.join(carpeta, "anaqueles.json"),
        os.path.join(carpeta, "spawn.json"),
    )

    # Config de features
    cfg = CONFIG_ESCENARIOS.get(params.escenario, SimConfig())

    # Política de tránsito
    movimientos, costos, no_stop = _cargar_politica_transito(params.escenario)

    # Construir simulación (len(spawns) por si se clampó)
    sim = SimAlmacen(
        grid=grid,
        estacion_dock=estacion_dock,
        anaquel_home=anaquel_home,
        robots=len(spawns),
        puntos_spawn=spawns,
        pedidos=pedidos,
        seed=params.seed,
        movimientos_permitidos=movimientos,
        costos_direccion=costos,
        celdas_no_stop=no_stop,
        config=cfg,
    )

    # Tracking visitas/esperas para heatmaps
    import numpy as _np
    alto, ancho = grid.shape
    _visitas = _np.zeros((alto, ancho), dtype=_np.int32)
    _esperas = _np.zeros((alto, ancho), dtype=_np.int32)

    # Correr todos los ticks (síncrono, sin sleep)
    for _ in range(params.ticks):
        sim.step()
        for r in sim.lista_robots:
            x, y = r.pos
            _visitas[y, x] += 1
            if r.estado == "esperando":
                _esperas[y, x] += 1

    metricas = sim.metricas()

    # Guardar opcionalmente
    if params.guardar:
        uid = get_current_user_id(request)
        etiqueta = (params.nombre or "").strip() or params.escenario
        run_id = crud.guardar_run(etiqueta, metricas, user_id=uid)
        metricas["run_id"] = run_id
        metricas["guardado_en_bd"] = True

        try:
            from visualiza_simulacion import guardar_heatmaps
            carpeta_hm = os.path.join("outputs", "runs", str(run_id))
            os.makedirs(carpeta_hm, exist_ok=True)
            guardar_heatmaps(grid, _visitas, _esperas, prefijo=os.path.join(carpeta_hm, "heatmap"))
            metricas["heatmaps_generados"] = True
            metricas["heatmaps"] = {
                "visitas": f"/metricas/heatmaps/{run_id}/visitas",
                "esperas": f"/metricas/heatmaps/{run_id}/esperas",
                "ratio":   f"/metricas/heatmaps/{run_id}/ratio",
            }
        except Exception:
            metricas["heatmaps_generados"] = False

    return metricas
