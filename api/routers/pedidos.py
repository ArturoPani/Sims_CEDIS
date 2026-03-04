"""
Router de pedidos — generación, listado y consulta de pedidos en la BD.
"""
import json
import os
from typing import Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from db import crud

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])


# ── Helpers (reutilizan lógica de generador_pedidos.py) ──────────

def _ruta_por_escenario(escenario: str, nombre_archivo: str) -> str:
    return os.path.join("outputs", escenario, nombre_archivo)


def _generar_pedidos(
    escenario: str,
    seed: int,
    cantidad: int,
    burst: bool = False,
) -> list[dict]:
    """Genera pedidos aleatorios a partir de estaciones y anaqueles del escenario."""
    ruta_estaciones = _ruta_por_escenario(escenario, "estaciones.json")
    ruta_anaqueles = _ruta_por_escenario(escenario, "anaqueles.json")

    if not os.path.isfile(ruta_estaciones):
        raise FileNotFoundError(f"No se encontró {ruta_estaciones}")
    if not os.path.isfile(ruta_anaqueles):
        raise FileNotFoundError(f"No se encontró {ruta_anaqueles}")

    with open(ruta_estaciones, "r", encoding="utf-8") as f:
        estaciones = json.load(f)
    with open(ruta_anaqueles, "r", encoding="utf-8") as f:
        anaqueles = json.load(f)

    ids_estacion = [e["estacion_id"] for e in estaciones]
    ids_anaquel = [a["anaquel_id"] for a in anaqueles]

    rng = np.random.default_rng(seed)
    pedidos = []

    for i in range(cantidad):
        estacion_id = int(rng.choice(ids_estacion))
        anaquel_id = int(rng.choice(ids_anaquel))

        if burst:
            tick_creacion = int(rng.integers(0, 2001)) if rng.random() < 0.70 else int(rng.integers(0, 10001))
        else:
            tick_creacion = 0

        pedidos.append({
            "pedido_id": i,
            "anaquel_id": anaquel_id,
            "estacion_id": estacion_id,
            "tick_creacion": tick_creacion,
        })

    return pedidos


# ── Schemas ──────────────────────────────────────────────────────

class GenerarPedidosIn(BaseModel):
    escenario: str
    seed: int = 42
    cantidad: int = 600
    burst: bool = False


class PedidoOut(BaseModel):
    pedido_id: int
    anaquel_id: int
    estacion_id: int
    tick_creacion: int
    escenario: str
    seed: int


# ── Endpoints ────────────────────────────────────────────────────

@router.get("", response_model=list[PedidoOut])
def listar_pedidos(
    escenario: str = Query(..., description="Nombre del escenario"),
    seed: Optional[int] = Query(None, description="Filtrar por seed"),
):
    """Lista los pedidos almacenados en la BD para un escenario."""
    return crud.listar_pedidos(escenario, seed=seed)


@router.post("/generar", status_code=201)
def generar_pedidos(params: GenerarPedidosIn):
    """
    Genera pedidos aleatorios y los guarda en la BD.
    Usa estaciones y anaqueles del escenario (archivos en disco).
    Si ya existen pedidos para ese escenario+seed, los reemplaza.
    """
    try:
        pedidos = _generar_pedidos(
            escenario=params.escenario,
            seed=params.seed,
            cantidad=params.cantidad,
            burst=params.burst,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Limpiar pedidos previos del mismo escenario+seed
    eliminados = crud.eliminar_pedidos(params.escenario, seed=params.seed)

    # Insertar nuevos
    insertados = crud.insertar_pedidos(pedidos, params.escenario, params.seed)

    return {
        "escenario": params.escenario,
        "seed": params.seed,
        "pedidos_generados": insertados,
        "pedidos_previos_eliminados": eliminados,
    }


@router.get("/{pedido_id}", response_model=PedidoOut)
def obtener_pedido(
    pedido_id: int,
    escenario: str = Query(..., description="Nombre del escenario"),
    seed: Optional[int] = Query(None, description="Seed del lote de pedidos"),
):
    """Obtiene un pedido específico por su ID."""
    pedidos = crud.listar_pedidos(escenario, seed=seed)
    for p in pedidos:
        if p["pedido_id"] == pedido_id:
            return p
    raise HTTPException(status_code=404, detail=f"Pedido {pedido_id} no encontrado.")


@router.delete("", status_code=200)
def eliminar_pedidos(
    escenario: str = Query(..., description="Nombre del escenario"),
    seed: Optional[int] = Query(None, description="Filtrar por seed (si se omite borra todos del escenario)"),
):
    """Elimina pedidos de un escenario (opcionalmente solo de un seed)."""
    eliminados = crud.eliminar_pedidos(escenario, seed=seed)
    return {"eliminados": eliminados}
