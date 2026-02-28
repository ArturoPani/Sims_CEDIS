#!/usr/bin/env python3
import argparse
import json
import os
from typing import Dict, List, Tuple

import matplotlib
import matplotlib.pyplot as plt
import numpy as np


def _cargar_metricas(ruta: str) -> Dict:
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def _es_numero(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def _direccion_metricas() -> Dict[str, str]:
    return {
        "pedidos_completados": "higher",
        "throughput_pedidos_por_1000_ticks": "higher",
        "utilizacion_promedio": "higher",
        "tiempo_promedio_pedido_ticks": "lower",
        "tiempo_promedio_espera_ticks": "lower",
        "deadlock": "lower",
        "eventos_alto": "lower",
        "distancia_total_celdas": "lower",
        "colisiones_vertice": "lower",
        "intercambios_arista": "lower",
    }


def _metricas_comparables(benchmark: Dict, actual: Dict) -> List[str]:
    inter = set(benchmark.keys()) & set(actual.keys())
    comparables = []
    for k in inter:
        if _es_numero(benchmark[k]) and _es_numero(actual[k]):
            if k in {"seed", "tick_final", "robots", "pedidos_totales"}:
                continue
            comparables.append(k)
    return sorted(comparables)


def _valor_bonito(v: float) -> str:
    if isinstance(v, int):
        return str(v)
    if abs(v) >= 1000:
        return f"{v:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{v:.4f}" if abs(v) < 1 else f"{v:.2f}"


def _etiqueta_metrica(metrica: str) -> str:
    nombres = {
        "pedidos_completados": "Pedidos",
        "throughput_pedidos_por_1000_ticks": "Throughput",
        "utilizacion_promedio": "Utilización",
        "tiempo_promedio_pedido_ticks": "T. pedido",
        "tiempo_promedio_espera_ticks": "T. espera",
        "deadlock": "Deadlock",
        "eventos_alto": "Altos",
        "distancia_total_celdas": "Distancia",
        "colisiones_vertice": "Col. vértice",
        "intercambios_arista": "Interc. arista",
    }
    return nombres.get(metrica, metrica.replace("_", " ").capitalize())


def _paleta_tema(tema: str) -> Dict[str, str]:
    if tema == "dark":
        return {
            "fig_bg": "#0b1220",
            "panel_bg": "#111827",
            "title": "#e5e7eb",
            "text": "#e5e7eb",
            "muted": "#9ca3af",
            "grid": "#334155",
            "axis": "#64748b",
            "zero": "#94a3b8",
            "bar_pos": "#22c55e",
            "bar_neg": "#ef4444",
            "bar_neu": "#64748b",
            "bar_edge": "#0f172a",
            "header_bg": "#1e3a8a",
            "header_text": "#dbeafe",
            "row_even": "#0f172a",
            "row_odd": "#111827",
            "state_neutral": "#1f2937",
            "state_good": "#052e16",
            "state_bad": "#450a0a",
            "state_good_text": "#86efac",
            "state_bad_text": "#fca5a5",
            "state_neutral_text": "#cbd5e1",
            "card_bg": "#1e293b",
            "card_edge": "#3b82f6",
            "banner": "#60a5fa",
            "table_edge": "#334155",
        }
    return {
        "fig_bg": "#eef4ff",
        "panel_bg": "#f8fbff",
        "title": "#1e293b",
        "text": "#111827",
        "muted": "#0f172a",
        "grid": "#64748b",
        "axis": "#94a3b8",
        "zero": "#334155",
        "bar_pos": "#22c55e",
        "bar_neg": "#ef4444",
        "bar_neu": "#94a3b8",
        "bar_edge": "#2d3748",
        "header_bg": "#dbeafe",
        "header_text": "#1f2937",
        "row_even": "#ffffff",
        "row_odd": "#f8fafc",
        "state_neutral": "#f1f5f9",
        "state_good": "#dcfce7",
        "state_bad": "#ffe4e6",
        "state_good_text": "#15803d",
        "state_bad_text": "#b91c1c",
        "state_neutral_text": "#374151",
        "card_bg": "#e0ecff",
        "card_edge": "#93c5fd",
        "banner": "#2563eb",
        "table_edge": "#d1d5db",
    }


def _evaluar_metricas(benchmark: Dict, actual: Dict, metricas: List[str]) -> List[Dict]:
    orientacion = _direccion_metricas()
    resultado = []

    for m in metricas:
        b = float(benchmark[m])
        a = float(actual[m])
        delta = a - b

        if b == 0:
            delta_pct_valor = np.nan
        else:
            delta_pct_valor = (delta / abs(b)) * 100.0

        sentido = orientacion.get(m, "higher")
        if sentido == "higher":
            score = ((a - b) / abs(b) * 100.0) if b != 0 else (100.0 if a > b else 0.0)
        else:
            score = ((b - a) / abs(b) * 100.0) if b != 0 else (100.0 if a < b else 0.0)

        if abs(a - b) < 1e-12:
            estado = "SIN_CAMBIO"
        elif score > 0:
            estado = "MEJORA"
        else:
            estado = "EMPEORA"

        resultado.append(
            {
                "metrica": m,
                "benchmark": b,
                "actual": a,
                "delta": delta,
                "delta_pct_valor": delta_pct_valor,
                "score": score,
                "estado": estado,
                "sentido": sentido,
            }
        )

    return resultado


def _dibujar_interfaz(resultados: List[Dict], ruta_salida: str, titulo: str, tema: str) -> None:
    if not resultados:
        raise RuntimeError("No hay métricas numéricas comparables entre benchmark y actual.")

    ordenados = sorted(resultados, key=lambda x: x["score"], reverse=True)
    nombres = [r["metrica"] for r in ordenados]
    nombres_legibles = [_etiqueta_metrica(n) for n in nombres]
    scores = [r["score"] for r in ordenados]
    paleta = _paleta_tema(tema)
    colores = [paleta["bar_pos"] if s > 0 else (paleta["bar_neg"] if s < 0 else paleta["bar_neu"]) for s in scores]

    fig = plt.figure(figsize=(18, 11), facecolor=paleta["fig_bg"])
    gs = fig.add_gridspec(2, 2, height_ratios=[2.0, 1.55], width_ratios=[2.45, 1.0])

    ax1 = fig.add_subplot(gs[0, :])
    ax1.set_facecolor(paleta["panel_bg"])
    y = np.arange(len(nombres))
    barras = ax1.barh(y, scores, color=colores, edgecolor=paleta["bar_edge"], linewidth=0.6)
    ax1.axvline(0, color=paleta["zero"], linewidth=1.1)
    ax1.set_yticks(y)
    ax1.set_yticklabels(nombres_legibles, fontsize=10, color=paleta["text"])
    ax1.invert_yaxis()
    ax1.set_xlabel("Impacto porcentual de desempeño vs benchmark (+ mejora / - empeora)", fontsize=11, color=paleta["text"])
    ax1.set_title(titulo, fontsize=15, fontweight="bold", color=paleta["title"])
    ax1.grid(axis="x", linestyle="--", alpha=0.22, color=paleta["grid"])
    ax1.tick_params(axis="x", colors=paleta["text"])
    for spine in ["top", "right"]:
        ax1.spines[spine].set_visible(False)
    ax1.spines["left"].set_color(paleta["axis"])
    ax1.spines["bottom"].set_color(paleta["axis"])

    max_abs = max(abs(s) for s in scores) if scores else 1.0
    limite = 1.0 if max_abs < 1.0 else max_abs * 1.20
    ax1.set_xlim(-limite, limite)

    desplazamiento = limite * 0.02

    for i, s in enumerate(scores):
        ax1.text(
            s + (desplazamiento if s >= 0 else -desplazamiento),
            i,
            f"{s:.2f}%",
            va="center",
            ha="left" if s >= 0 else "right",
            fontsize=9,
            color=paleta["muted"],
        )

    for b in barras:
        b.set_alpha(0.9)

    ax2 = fig.add_subplot(gs[1, 0])
    ax2.set_facecolor(paleta["panel_bg"])
    ax2.axis("off")
    columnas = ["Métrica", "Benchmark", "Actual", "Δ valor", "Δ % valor", "Estado"]
    filas = []
    for r in ordenados:
        delta_pct = "N/A" if np.isnan(r["delta_pct_valor"]) else f"{r['delta_pct_valor']:.2f}%"
        filas.append(
            [
                _etiqueta_metrica(r["metrica"]),
                _valor_bonito(r["benchmark"]),
                _valor_bonito(r["actual"]),
                _valor_bonito(r["delta"]),
                delta_pct,
                r["estado"],
            ]
        )

    tabla = ax2.table(cellText=filas, colLabels=columnas, loc="upper left", bbox=[0.0, 0.0, 1.0, 0.98])
    tabla.auto_set_font_size(False)
    tabla.set_fontsize(8.6)
    tabla.scale(1.0, 1.30)

    for (fila, col), celda in tabla.get_celld().items():
        celda.set_edgecolor(paleta["table_edge"])
        celda.set_linewidth(0.8)
        if fila == 0:
            celda.set_facecolor(paleta["header_bg"])
            celda.set_text_props(weight="bold", color=paleta["header_text"])
        else:
            estado = filas[fila - 1][-1]
            color_fila = paleta["row_even"] if fila % 2 == 0 else paleta["row_odd"]
            if estado == "MEJORA":
                celda.set_facecolor(paleta["state_good"] if col == 5 else color_fila)
            elif estado == "EMPEORA":
                celda.set_facecolor(paleta["state_bad"] if col == 5 else color_fila)
            else:
                celda.set_facecolor(paleta["state_neutral"] if col == 5 else color_fila)
            if col != 5:
                celda.set_text_props(color=paleta["text"])
            if col == 5:
                color_estado = (
                    paleta["state_good_text"]
                    if estado == "MEJORA"
                    else (paleta["state_bad_text"] if estado == "EMPEORA" else paleta["state_neutral_text"])
                )
                celda.set_text_props(weight="bold", color=color_estado)

    ax3 = fig.add_subplot(gs[1, 1])
    ax3.set_facecolor(paleta["panel_bg"])
    ax3.axis("off")
    mejoras = [r for r in resultados if r["estado"] == "MEJORA"]
    empeoras = [r for r in resultados if r["estado"] == "EMPEORA"]
    iguales = [r for r in resultados if r["estado"] == "SIN_CAMBIO"]

    mejor = max(resultados, key=lambda x: x["score"])
    peor = min(resultados, key=lambda x: x["score"])

    resumen = (
        f"Resumen\n\n"
        f"Métricas comparadas: {len(resultados)}\n"
        f"Mejoran: {len(mejoras)}\n"
        f"Empeoran: {len(empeoras)}\n"
        f"Sin cambio: {len(iguales)}\n\n"
        f"Mayor mejora:\n"
        f"{_etiqueta_metrica(mejor['metrica'])} ({mejor['score']:.2f}%)\n\n"
        f"Mayor deterioro:\n"
        f"{_etiqueta_metrica(peor['metrica'])} ({peor['score']:.2f}%)"
    )
    ax3.text(
        0.03,
        0.97,
        resumen,
        va="top",
        fontsize=11,
        color=paleta["text"],
        bbox={"facecolor": paleta["card_bg"], "edgecolor": paleta["card_edge"], "boxstyle": "round,pad=0.7"},
    )

    plt.figtext(
        0.015,
        0.975,
        "Comparador visual de desempeño",
        ha="left",
        va="top",
        fontsize=12,
        color=paleta["banner"],
        fontweight="bold",
    )

    plt.subplots_adjust(left=0.12, right=0.985, top=0.94, bottom=0.05, hspace=0.30, wspace=0.20)
    plt.savefig(ruta_salida, dpi=220)
    if "agg" not in matplotlib.get_backend().lower():
        plt.show()
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(
        description="Compara métricas actuales contra benchmark y muestra una interfaz visual.",
    )
    parser.add_argument(
        "--benchmark",
        type=str,
        default=os.path.join("outputs", "benchmark", "metricas.json"),
        help="Ruta al metricas.json base (benchmark).",
    )
    parser.add_argument(
        "--actual",
        type=str,
        required=True,
        help="Ruta al metricas.json actual a comparar.",
    )
    parser.add_argument(
        "--salida",
        type=str,
        default=None,
        help="PNG de salida para la comparación visual.",
    )
    parser.add_argument(
        "--tema",
        type=str,
        default="dark",
        choices=["light", "dark"],
        help="Tema visual del reporte (light o dark).",
    )

    args = parser.parse_args()

    benchmark = _cargar_metricas(args.benchmark)
    actual = _cargar_metricas(args.actual)

    metricas = _metricas_comparables(benchmark, actual)
    resultados = _evaluar_metricas(benchmark, actual, metricas)

    if args.salida:
        salida = args.salida
    else:
        salida = os.path.join(os.path.dirname(args.actual), "comparacion_vs_benchmark.png")

    os.makedirs(os.path.dirname(salida) or ".", exist_ok=True)

    titulo = f"Comparación de métricas vs benchmark ({args.tema})"
    _dibujar_interfaz(resultados, salida, titulo, args.tema)

    print(f"[OK] Comparación visual guardada en: {salida}")
    print("[OK] Resumen por métrica:")
    for r in sorted(resultados, key=lambda x: x["score"], reverse=True):
        print(
            f"  - {r['metrica']}: {r['estado']} | "
            f"impacto={r['score']:.2f}% | "
            f"Δvalor={r['delta']:.4f}"
        )


if __name__ == "__main__":
    main()
