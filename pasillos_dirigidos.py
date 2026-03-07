#!/usr/bin/env python3
"""
Motor de política de tránsito para pasillos dirigidos.

Estrategia **híbrida**:
  - **Restricciones duras** (movimientos_permitidos) en pasillos de
    estantería entre cross-aisles.  Cada columna de rack se dirige en
    un sentido alterno (N/S), eliminando estructuralmente los encuentros
    frontales.
  - **Costos direccionales** (costos_direccion) suaves en cross-aisles
    y zona de entregas.  Guían al tráfico sin bloquear rutas.

Estructura del layout detectada automáticamente:
  - Pasillos de estantería (1 celda de ancho, flanqueados por racks):
    sentido alterno N/S según paridad de la columna.
  - Cross-aisles (filas abiertas sin racks): totalmente abiertas,
    con costo suave para preferir sentido alterno E/O.
  - Zona de entregas (últimas filas antes de estaciones):
    guía suave de circulación E/O sin restricciones duras.
  - Corredores/áreas amplias: sin restricción ni costo.
"""
import json
import os
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

LIBRE = 0
ANAQUEL = 1
ESTACION = 2
BLOQUEADO = 3

Celda = Tuple[int, int]
Direccion = Tuple[int, int]

# Direcciones canónicas
NORTE = (0, -1)
SUR   = (0, 1)
ESTE  = (1, 0)
OESTE = (-1, 0)
TODAS = [NORTE, SUR, ESTE, OESTE]


def _es_transitable(grid: np.ndarray, x: int, y: int) -> bool:
    alto, ancho = grid.shape
    if x < 0 or x >= ancho or y < 0 or y >= alto:
        return False
    return int(grid[y, x]) in (LIBRE, ESTACION)


def _ancho_local(grid: np.ndarray, x: int, y: int, eje: str) -> int:
    """
    Mide el ancho *local* del corredor al que pertenece (x,y).

    eje='h' → cuenta celdas consecutivas en la misma fila (ancho del pasillo vertical).
    eje='v' → cuenta celdas consecutivas en la misma columna (ancho del pasillo horizontal).
    """
    alto, ancho = grid.shape
    if not _es_transitable(grid, x, y):
        return 0

    if eje == "h":
        izq = x
        while izq - 1 >= 0 and _es_transitable(grid, izq - 1, y):
            izq -= 1
        der = x
        while der + 1 < ancho and _es_transitable(grid, der + 1, y):
            der += 1
        return der - izq + 1
    else:
        arriba = y
        while arriba - 1 >= 0 and _es_transitable(grid, x, arriba - 1):
            arriba -= 1
        abajo = y
        while abajo + 1 < alto and _es_transitable(grid, x, abajo + 1):
            abajo += 1
        return abajo - arriba + 1


def _es_pasillo_rack(grid: np.ndarray, x: int, y: int) -> bool:
    """
    True si (x,y) es una celda de pasillo de estantería: transitable,
    flanqueada por al menos un rack (ANAQUEL) en el eje horizontal.
    """
    alto, ancho = grid.shape
    if not _es_transitable(grid, x, y):
        return False
    rack_izq = (x - 1 >= 0 and int(grid[y, x - 1]) == ANAQUEL)
    rack_der = (x + 1 < ancho and int(grid[y, x + 1]) == ANAQUEL)
    return rack_izq or rack_der


def _es_cross_aisle(grid: np.ndarray, x: int, y: int) -> bool:
    """
    True si (x,y) pertenece a una fila abierta (cross-aisle) entre bloques
    de racks.  Se define como fila donde *no hay racks* en un vecindario amplio.
    """
    alto, ancho = grid.shape
    if not _es_transitable(grid, x, y):
        return False
    # Verificar que la fila no tenga racks en un rango local razonable (±30 cols)
    x_lo = max(0, x - 30)
    x_hi = min(ancho, x + 31)
    for xi in range(x_lo, x_hi):
        if int(grid[y, xi]) == ANAQUEL:
            return False
    return True


def generar_politica(
    grid: np.ndarray,
    estaciones: List[Dict],
    penalidad_cross: float = 1.5,
    penalidad_delivery: float = 1.5,
) -> Dict:
    """
    Genera la política de tránsito híbrida.

    Parámetros:
      penalidad_cross    : costo extra por ir contra el sentido preferido
                           en cross-aisles.
      penalidad_delivery : costo extra por ir contra circulación en la
                           zona de entregas.

    Regresa un dict con:
      - "movimientos": { "x,y": [[dx,dy], ...] }
        Direcciones permitidas (restricción dura) para pasillos de rack.
      - "costos_direccion": { "x,y,dx,dy": float }
        Costo extra (guía suave) para cross-aisles y zona de entregas.
      - "no_stop": ["x,y", ...]
        Celdas donde no se permite detenerse (docks).
    """
    alto, ancho_grid = grid.shape

    # Identificar zona de entregas
    if estaciones:
        docks = set(tuple(e["dock"]) for e in estaciones)
        y_buffer = next(iter(docks))[1]
    else:
        docks = set()
        y_buffer = alto - 3

    # Zona de entregas: desde 4 filas arriba del buffer hasta el buffer
    y_delivery_top = y_buffer - 4

    movimientos: Dict[str, List[List[int]]] = {}
    costos_dir: Dict[str, float] = {}
    no_stop: List[str] = []

    for y in range(alto):
        for x in range(ancho_grid):
            if not _es_transitable(grid, x, y):
                continue

            key_base = f"{x},{y}"
            ah = _ancho_local(grid, x, y, "h")

            # ── Zona de entregas (soft) ──
            if y >= y_delivery_top and y <= y_buffer:
                fila_rel = y - y_delivery_top
                if fila_rel % 2 == 0:
                    dir_contra = OESTE
                else:
                    dir_contra = ESTE

                k_contra = f"{x},{y},{dir_contra[0]},{dir_contra[1]}"
                costos_dir[k_contra] = penalidad_delivery

                if (x, y) in docks:
                    no_stop.append(key_base)
                continue

            # ── Pasillo de rack: hard one-way ──
            if ah == 1 and _es_pasillo_rack(grid, x, y):
                # Sentido alterno: pares → SUR, impares → NORTE
                if x % 2 == 0:
                    dir_ok = SUR
                else:
                    dir_ok = NORTE

                # Permitir: dirección del pasillo + laterales para entrar/salir
                dirs_filtradas = []
                for d in [dir_ok, ESTE, OESTE]:
                    nx, ny = x + d[0], y + d[1]
                    if _es_transitable(grid, nx, ny):
                        dirs_filtradas.append(list(d))
                # Fallback de seguridad
                if not dirs_filtradas:
                    for d in TODAS:
                        nx, ny = x + d[0], y + d[1]
                        if _es_transitable(grid, nx, ny):
                            dirs_filtradas.append(list(d))
                if dirs_filtradas:
                    movimientos[key_base] = dirs_filtradas
                continue

            # ── Cross-aisle (soft) ──
            if _es_cross_aisle(grid, x, y):
                av = _ancho_local(grid, x, y, "v")
                if av <= 6:
                    y_start = y
                    while y_start - 1 >= 0 and _es_cross_aisle(grid, x, y_start - 1):
                        y_start -= 1
                    fila_rel = y - y_start

                    if fila_rel % 2 == 0:
                        dir_contra = OESTE
                    else:
                        dir_contra = ESTE

                    k_contra = f"{x},{y},{dir_contra[0]},{dir_contra[1]}"
                    costos_dir[k_contra] = penalidad_cross
                continue

            # ── Corredor amplio: sin restricción ──

    return {
        "movimientos": movimientos,
        "costos_direccion": costos_dir,
        "no_stop": no_stop,
    }


def guardar_politica(politica: Dict, ruta: str) -> None:
    """Serializa la política a JSON."""
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(politica, f, ensure_ascii=False)


def cargar_politica(ruta: str) -> Dict:
    """Carga la política desde JSON."""
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def politica_a_restricciones(politica: Dict) -> Tuple[
    Optional[Dict[Celda, List[Direccion]]],
    Optional[Dict[Tuple[int, int, int, int], float]],
    Optional[Set[Celda]],
]:
    """
    Convierte la política serializada a estructuras usables por a_estrella y sim_core.

    Regresa:
      - movimientos_permitidos: {(x,y): [(dx,dy), ...]} o None
        Restricciones duras para pasillos de rack.
      - costos_direccion: {(x, y, dx, dy): float} o None
        Costos suaves para cross-aisles y delivery.
      - celdas_no_stop: {(x,y), ...} o None
    """
    if not politica:
        return None, None, None

    # Movimientos permitidos (hard)
    mov = politica.get("movimientos", {})
    movimientos_permitidos: Dict[Celda, List[Direccion]] = {}
    for key, dirs in mov.items():
        x, y = [int(v) for v in key.split(",")]
        movimientos_permitidos[(x, y)] = [tuple(d) for d in dirs]

    # Costos direccionales (soft)
    raw = politica.get("costos_direccion", {})
    costos_direccion: Dict[Tuple[int, int, int, int], float] = {}
    for key, val in raw.items():
        parts = key.split(",")
        x, y, dx, dy = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
        costos_direccion[(x, y, dx, dy)] = float(val)

    # No-stop
    ns = politica.get("no_stop", [])
    celdas_no_stop: Set[Celda] = set()
    for key in ns:
        x, y = [int(v) for v in key.split(",")]
        celdas_no_stop.add((x, y))

    return (
        movimientos_permitidos if movimientos_permitidos else None,
        costos_direccion if costos_direccion else None,
        celdas_no_stop if celdas_no_stop else None,
    )
