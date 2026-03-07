#!/usr/bin/env python3
"""
Genera la política de tránsito dirigido para un escenario existente.

Uso:
  python generar_politica.py --escenario benchmark

Lee:
  outputs/<escenario>/layout.npy
  outputs/<escenario>/estaciones.json

Escribe:
  outputs/<escenario>/politica_transito.json
"""
import argparse
import json
import os

import numpy as np

from out_paths import asegurar_dirs_de_salidas
from pasillos_dirigidos import generar_politica, guardar_politica


def _ruta_por_escenario(escenario: str, nombre_archivo: str) -> str:
    return os.path.join("outputs", escenario, nombre_archivo)


def main():
    parser = argparse.ArgumentParser(
        description="Genera política de tránsito dirigido para un escenario.",
    )
    parser.add_argument(
        "--escenario",
        type=str,
        default="benchmark",
        help="Nombre del escenario. Lee de outputs/<escenario>/ y escribe ahí.",
    )
    parser.add_argument(
        "--penalidad_cross",
        type=float,
        default=1.5,
        help="Penalización por ir contra el sentido preferido en cross-aisles.",
    )
    parser.add_argument(
        "--penalidad_delivery",
        type=float,
        default=1.5,
        help="Penalización por ir contra circulación en zona de entregas.",
    )
    parser.add_argument(
        "--layout",
        type=str,
        default=None,
        help="(Opcional) Ruta explícita a layout.npy.",
    )
    parser.add_argument(
        "--estaciones",
        type=str,
        default=None,
        help="(Opcional) Ruta explícita a estaciones.json.",
    )
    parser.add_argument(
        "--salida",
        type=str,
        default=None,
        help="(Opcional) Ruta explícita de salida para politica_transito.json.",
    )

    args = parser.parse_args()

    ruta_layout = args.layout or _ruta_por_escenario(args.escenario, "layout.npy")
    ruta_estaciones = args.estaciones or _ruta_por_escenario(args.escenario, "estaciones.json")
    ruta_salida = args.salida or _ruta_por_escenario(args.escenario, "politica_transito.json")

    asegurar_dirs_de_salidas([ruta_salida])

    grid = np.load(ruta_layout)

    with open(ruta_estaciones, "r", encoding="utf-8") as f:
        estaciones = json.load(f)

    politica = generar_politica(
        grid, estaciones,
        penalidad_cross=args.penalidad_cross,
        penalidad_delivery=args.penalidad_delivery,
    )
    guardar_politica(politica, ruta_salida)

    n_mov = len(politica["movimientos"])
    n_costos = len(politica["costos_direccion"])
    n_nostop = len(politica["no_stop"])

    print(f"[OK] Escenario : {args.escenario}")
    print(f"[OK] Política  : {ruta_salida}")
    print(f"  Celdas one-way (hard) : {n_mov}")
    print(f"  Costos direccionales  : {n_costos}")
    print(f"  Celdas no-stop        : {n_nostop}")


if __name__ == "__main__":
    main()
