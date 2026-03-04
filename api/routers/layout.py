"""
Router de layout — sirve el grid del almacén para renderizar en el frontend.
"""
import os
import numpy as np
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/layout", tags=["Layout"])


@router.get("")
def obtener_layout(
    escenario: str = Query("benchmark", description="Nombre del escenario"),
):
    """
    Devuelve el grid del almacén como JSON.
    Cada celda tiene un tipo: 0=libre, 1=obstáculo/anaquel, 2=estación, 3=otro.
    El grid se envía como lista de filas (row-major).
    """
    ruta = os.path.join("outputs", escenario, "layout.npy")
    if not os.path.isfile(ruta):
        raise HTTPException(status_code=404, detail=f"Layout no encontrado: {ruta}")

    grid = np.load(ruta)
    alto, ancho = grid.shape

    return JSONResponse(content={
        "escenario": escenario,
        "alto": alto,
        "ancho": ancho,
        "grid": grid.tolist(),
    })
