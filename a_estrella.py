#!/usr/bin/env python3
import heapq
from typing import Dict, List, Optional, Tuple
import numpy as np

LIBRE = 0
ESTACION = 2  # transitable
# ANAQUEL y BLOQUEADO son obstáculos

Celda = Tuple[int, int]
Direccion = Tuple[int, int]


def a_estrella(
    grid: np.ndarray,
    inicio: Celda,
    meta: Celda,
    movimientos_permitidos: Optional[Dict[Celda, List[Direccion]]] = None,
    costos_direccion: Optional[Dict[Tuple[int, int, int, int], float]] = None,
) -> Optional[List[Celda]]:
    """
    Algoritmo A* sobre un grid 4-conectado (arriba/abajo/izquierda/derecha).

    Parámetros opcionales (pasillos dirigidos):
      - movimientos_permitidos: {(x,y): [(dx,dy), ...]}
        Si se proporciona, solo expande las direcciones permitidas para la
        celda actual.  Si la celda no está en el dict, se permiten las 4.
      - costos_direccion: {(x, y, dx, dy): float}
        Costo adicional por moverse desde (x,y) en dirección (dx,dy).
        NO restringe — solo desincentiva.

    Ambos pueden usarse simultáneamente.

    Regresa:
      - Una ruta (lista de celdas) que incluye inicio y meta, o
      - None si la meta no es alcanzable.

    Convención del grid:
      - LIBRE (=0) y ESTACION (=2) son transitables.
      - Cualquier otro valor se considera obstáculo.
    """
    alto, ancho = grid.shape

    def en_rango(x: int, y: int) -> bool:
        return 0 <= x < ancho and 0 <= y < alto

    def transitable(x: int, y: int) -> bool:
        return grid[y, x] in (LIBRE, ESTACION)

    ix, iy = inicio
    mx, my = meta

    # Validación rápida
    if (
        (not en_rango(ix, iy))
        or (not en_rango(mx, my))
        or (not transitable(ix, iy))
        or (not transitable(mx, my))
    ):
        return None

    todas_dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    def heuristica(x: int, y: int) -> float:
        # Distancia Manhattan
        return abs(x - mx) + abs(y - my)

    # heap: (f = g + h, g, (x,y))
    abiertos: List[Tuple[float, float, Celda]] = []
    heapq.heappush(abiertos, (heuristica(ix, iy), 0.0, (ix, iy)))

    vino_de: Dict[Celda, Celda] = {}
    costo_g: Dict[Celda, float] = {(ix, iy): 0.0}
    cerrados = set()

    while abiertos:
        _, g_actual, actual = heapq.heappop(abiertos)

        if actual in cerrados:
            continue
        cerrados.add(actual)

        if actual == (mx, my):
            # Reconstrucción de ruta
            ruta = [actual]
            while actual in vino_de:
                actual = vino_de[actual]
                ruta.append(actual)
            ruta.reverse()
            return ruta

        x, y = actual

        # Determinar direcciones a expandir
        if movimientos_permitidos is not None and actual in movimientos_permitidos:
            dirs = movimientos_permitidos[actual]
        else:
            dirs = todas_dirs

        for dx, dy in dirs:
            nx, ny = x + dx, y + dy

            if (not en_rango(nx, ny)) or (not transitable(nx, ny)):
                continue

            extra = 0.0
            if costos_direccion is not None:
                extra = costos_direccion.get((x, y, dx, dy), 0.0)

            nuevo_g = g_actual + 1.0 + extra
            if nuevo_g < costo_g.get((nx, ny), 1e18):
                costo_g[(nx, ny)] = nuevo_g
                vino_de[(nx, ny)] = (x, y)
                heapq.heappush(abiertos, (nuevo_g + heuristica(nx, ny), nuevo_g, (nx, ny)))

    return None
