"""
Endpoints para consulta y comparación de métricas de runs guardados en Azure SQL.
Reutiliza la lógica de comparar_metricas.py sin depender de matplotlib.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import sys, os, math

# Asegurar que el raíz del proyecto esté en el path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from db.crud import listar_runs
from comparar_metricas import (
    _metricas_comparables,
    _evaluar_metricas,
    _etiqueta_metrica,
    _direccion_metricas,
)

router = APIRouter(prefix="/metricas", tags=["metricas"])

# ── Columnas numéricas comparables almacenadas en la tabla runs ──────────────
COLUMNAS_RUNS = [
    "pedidos_completados",
    "throughput_pedidos_por_1000t",
    "tiempo_promedio_pedido_ticks",
    "tiempo_promedio_espera_ticks",
    "utilizacion_promedio",
    "colisiones_vertice",
    "intercambios_arista",
    "deadlock",
    "eventos_alto",
    "distancia_total_celdas",
    "relevos",
]

# Mapeo de nombre de columna DB → clave usada en comparar_metricas
COL_MAP = {
    "throughput_pedidos_por_1000t": "throughput_pedidos_por_1000_ticks",
}


def _run_a_dict_metricas(run: dict) -> dict:
    """Convierte un row de 'runs' al dict de métricas que espera comparar_metricas."""
    out = {}
    for col in COLUMNAS_RUNS:
        clave = COL_MAP.get(col, col)
        val = run.get(col)
        if val is not None:
            out[clave] = float(val)
    # Campos de contexto (no comparables pero útiles)
    for extra in ("seed", "num_robots", "ticks", "pedidos_totales"):
        if run.get(extra) is not None:
            out[extra if extra != "num_robots" else "robots"] = run[extra]
    return out


# ════════════════════════════════════════════════════════════════
#  GET /metricas/runs
# ════════════════════════════════════════════════════════════════
@router.get("/runs")
def get_runs(escenario: Optional[str] = Query(None)):
    """Lista todas las corridas guardadas, opcionalmente filtradas por escenario."""
    try:
        runs = listar_runs(escenario)
        return runs
    except Exception as e:
        raise HTTPException(500, str(e))


# ════════════════════════════════════════════════════════════════
#  GET /metricas/disponibles
# ════════════════════════════════════════════════════════════════
@router.get("/disponibles")
def get_metricas_disponibles():
    """Devuelve las métricas disponibles para comparar con sus etiquetas y orientación."""
    orientacion = _direccion_metricas()
    metricas = []
    for col in COLUMNAS_RUNS:
        clave = COL_MAP.get(col, col)
        metricas.append({
            "clave": clave,
            "etiqueta": _etiqueta_metrica(clave),
            "orientacion": orientacion.get(clave, "higher"),
        })
    return metricas


# ════════════════════════════════════════════════════════════════
#  POST /metricas/comparar
# ════════════════════════════════════════════════════════════════
class ComparacionRequest(BaseModel):
    run_id_base: int           # run que actúa como benchmark
    run_id_actual: int         # run a comparar
    metricas: Optional[List[str]] = None   # None = todas las disponibles


@router.post("/comparar")
def comparar(req: ComparacionRequest):
    """Compara dos runs y devuelve resultados de evaluación."""
    try:
        runs = listar_runs()
        mapa = {r["run_id"]: r for r in runs}

        if req.run_id_base not in mapa:
            raise HTTPException(404, f"run_id {req.run_id_base} no encontrado")
        if req.run_id_actual not in mapa:
            raise HTTPException(404, f"run_id {req.run_id_actual} no encontrado")

        base_dict = _run_a_dict_metricas(mapa[req.run_id_base])
        actual_dict = _run_a_dict_metricas(mapa[req.run_id_actual])

        # Métricas disponibles entre ambos runs
        disponibles = _metricas_comparables(base_dict, actual_dict)

        # Filtrar las que pidió el usuario (si especificó)
        if req.metricas:
            seleccionadas = [m for m in req.metricas if m in disponibles]
        else:
            seleccionadas = disponibles

        if not seleccionadas:
            raise HTTPException(400, "No hay métricas comparables entre los runs seleccionados")

        resultados = _evaluar_metricas(base_dict, actual_dict, seleccionadas)

        # Enriquecer con etiquetas y sanitizar NaN / Infinity
        for r in resultados:
            r["etiqueta"] = _etiqueta_metrica(r["metrica"])
            for k, v in r.items():
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    r[k] = None

        return {
            "run_base": {
                "run_id": req.run_id_base,
                "escenario": mapa[req.run_id_base].get("escenario"),
                "fecha": str(mapa[req.run_id_base].get("fecha", "")),
                "seed": mapa[req.run_id_base].get("seed"),
            },
            "run_actual": {
                "run_id": req.run_id_actual,
                "escenario": mapa[req.run_id_actual].get("escenario"),
                "fecha": str(mapa[req.run_id_actual].get("fecha", "")),
                "seed": mapa[req.run_id_actual].get("seed"),
            },
            "resultados": resultados,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
