import json
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import numpy as np
from pathlib import Path

# ── Clasificación de métricas ─────────────────────────────────────────────────
EXCLUIR = {"colisiones_vertice", "intercambios_arista"}

MENOR_ES_MEJOR = {
    "tiempo_promedio_pedido_ticks",
    "tiempo_promedio_espera_ticks",
    "deadlock",
    "eventos_alto",
    "distancia_total_celdas",
}

MAYOR_ES_MEJOR = {
    "pedidos_completados",
    "throughput_pedidos_por_1000_ticks",
    "utilizacion_promedio",
}

CONTEXTO = {"seed", "tick_final", "robots", "pedidos_totales"}

LABELS = {
    "tiempo_promedio_pedido_ticks":   "T. promedio pedido (ticks)",
    "tiempo_promedio_espera_ticks":   "T. promedio espera (ticks)",
    "deadlock":                       "Deadlocks",
    "eventos_alto":                   "Eventos alto",
    "distancia_total_celdas":         "Distancia total (celdas)",
    "pedidos_completados":            "Pedidos completados",
    "throughput_pedidos_por_1000_ticks": "Throughput (/1000 ticks)",
    "utilizacion_promedio":           "Utilización promedio",
}

# ── Paleta visual ─────────────────────────────────────────────────────────────
C_BG     = "#0d1117"
C_PANEL  = "#161b22"
C_HEADER = "#1f2d3d"
C_BORDER = "#30363d"
C_TEXT   = "#e6edf3"
C_MUTED  = "#8b949e"
C_CYAN   = "#58a6ff"
C_GREEN  = "#3fb950"
C_RED    = "#f85149"
C_NEUTRO = "#6e7681"

# ── Terminal ANSI ─────────────────────────────────────────────────────────────
GREEN = "\033[92m"
RED   = "\033[91m"
CYAN  = "\033[96m"
RESET = "\033[0m"
BOLD  = "\033[1m"


# ── Lógica ────────────────────────────────────────────────────────────────────
def cargar_json(path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def calcular_cambio(base: float, nuevo: float):
    if base == 0:
        return None
    return ((nuevo - base) / abs(base)) * 100


def es_mejora(metrica: str, cambio: float):
    if metrica in MAYOR_ES_MEJOR:
        return cambio > 0
    if metrica in MENOR_ES_MEJOR:
        return cambio < 0
    return None


# ── Terminal ──────────────────────────────────────────────────────────────────
def comparar_terminal(base: dict, nuevo: dict) -> tuple[int, int]:
    print(f"\n{BOLD}{'='*62}{RESET}")
    print(f"{BOLD}  COMPARACIÓN DE MÉTRICAS{RESET}")
    print(f"{BOLD}{'='*62}{RESET}\n")

    print(f"{CYAN}{'Parámetro':<35} {'Base':>12} {'Nuevo':>12}{RESET}")
    print("-" * 62)
    for k in CONTEXTO:
        if k in base and k in nuevo:
            print(f"  {k:<33} {str(base[k]):>12} {str(nuevo[k]):>12}")

    print(f"\n{BOLD}{'Metrica':<35} {'Base':>10} {'Nuevo':>10} {'Cambio%':>10} {'Estado':>9}{RESET}")
    print("-" * 77)

    todas = (MAYOR_ES_MEJOR | MENOR_ES_MEJOR) - EXCLUIR
    mejoras = empeoradas = 0

    for metrica in sorted(todas):
        if metrica not in base or metrica not in nuevo:
            continue
        val_base = base[metrica]
        val_nuevo = nuevo[metrica]
        cambio = calcular_cambio(val_base, val_nuevo)

        if cambio is None:
            signo, estado, color = "N/A", "?", ""
        else:
            signo = f"{cambio:+.1f}%"
            bueno = es_mejora(metrica, cambio)
            if bueno is True:
                color, estado = GREEN, "MEJORA"
                mejoras += 1
            elif bueno is False:
                color, estado = RED, "EMPEORA"
                empeoradas += 1
            else:
                color, estado = "", "="

        print(f"{color}  {metrica[:33]:<33} {val_base:>10.4g} {val_nuevo:>10.4g} "
              f"{signo:>10}  {estado}{RESET}")

    total = mejoras + empeoradas
    print(f"\n{BOLD}{'='*62}{RESET}")
    print(f"  Métricas mejoradas : {GREEN}{mejoras}{RESET}")
    print(f"  Métricas empeoradas: {RED}{empeoradas}{RESET}")
    if total > 0:
        pct = (mejoras / total) * 100
        print(f"  Tasa de mejora     : {BOLD}{pct:.1f}%{RESET} ({mejoras}/{total})")
    print(f"{BOLD}{'='*62}{RESET}\n")

    return mejoras, empeoradas


# ── Ventana gráfica ───────────────────────────────────────────────────────────
def mostrar_ventana(base: dict, nuevo: dict, mejoras: int, empeoradas: int) -> None:
    todas = sorted((MAYOR_ES_MEJOR | MENOR_ES_MEJOR) - EXCLUIR)

    # Recopilar datos
    rows_table, cambios_plot, colores, estados = [], [], [], []
    for m in todas:
        vb = base.get(m, 0)
        vn = nuevo.get(m, 0)
        cambio = calcular_cambio(vb, vn)
        bueno  = es_mejora(m, cambio) if cambio is not None else None

        if cambio is None:
            c_str, estado, color = "N/A", "—", C_NEUTRO
        else:
            c_str = f"{cambio:+.1f}%"
            if bueno is True:
                estado, color = "MEJORA", C_GREEN
            elif bueno is False:
                estado, color = "EMPEORA", C_RED
            else:
                estado, color = "=", C_NEUTRO

        vb_str = f"{vb:.4g}" if isinstance(vb, float) else str(vb)
        vn_str = f"{vn:.4g}" if isinstance(vn, float) else str(vn)
        rows_table.append([LABELS.get(m, m), vb_str, vn_str, c_str, estado])
        cambios_plot.append(cambio if cambio is not None else 0)
        colores.append(color)
        estados.append(estado)

    n = len(todas)
    total = mejoras + empeoradas
    pct   = (mejoras / total * 100) if total > 0 else 0

    # ── Figura — layout apilado (1 columna, 4 filas) ──────────────────────────
    fig = plt.figure(figsize=(20, 14), facecolor=C_BG)
    try:
        fig.canvas.manager.set_window_title("CEDIS — Comparación de Métricas")
    except Exception:
        pass

    gs = gridspec.GridSpec(
        4, 1,
        figure=fig,
        height_ratios=[0.055, 0.33, 0.43, 0.185],
        hspace=0.38,
        left=0.25, right=0.97, top=0.97, bottom=0.04,
    )

    # ── Encabezado ────────────────────────────────────────────────────────────
    ax_hdr = fig.add_subplot(gs[0])
    ax_hdr.set_facecolor(C_HEADER)
    for sp in ax_hdr.spines.values():
        sp.set_edgecolor(C_CYAN)
        sp.set_linewidth(1.5)
    ax_hdr.axis('off')

    ax_hdr.text(0.5, 0.58, "COMPARACIÓN DE MÉTRICAS — SIMULACIÓN CEDIS",
                ha='center', va='center', fontsize=17, fontweight='bold',
                color=C_TEXT, transform=ax_hdr.transAxes)
    ctx_izq = "Base: M1.json     Nuevo: M2.json"
    ctx_der = "   ".join(f"{k}: {base.get(k,'?')}"
                         for k in ["seed", "robots", "tick_final", "pedidos_totales"])
    ax_hdr.text(0.02, 0.14, ctx_izq, ha='left', va='center', fontsize=9,
                color=C_CYAN, transform=ax_hdr.transAxes)
    ax_hdr.text(0.98, 0.14, ctx_der, ha='right', va='center', fontsize=9,
                color=C_MUTED, transform=ax_hdr.transAxes)

    # ── Tabla (ancho completo) ────────────────────────────────────────────────
    ax_tbl = fig.add_subplot(gs[1])
    ax_tbl.set_facecolor(C_PANEL)
    ax_tbl.axis('off')
    ax_tbl.set_title("  Tabla Comparativa", color=C_TEXT, fontsize=12,
                      fontweight='bold', loc='left', pad=10)

    col_headers = ["Métrica", "Escenario Base", "Nuevo Escenario", "Cambio %", "Resultado"]
    col_widths   = [0.30, 0.17, 0.17, 0.14, 0.14]

    cell_colors = []
    for est in estados:
        if est == "MEJORA":
            bg = ["#0c1f15"] * 5
        elif est == "EMPEORA":
            bg = ["#1f0c0c"] * 5
        else:
            bg = [C_PANEL] * 5
        cell_colors.append(bg)

    tbl = ax_tbl.table(
        cellText=rows_table,
        colLabels=col_headers,
        colWidths=col_widths,
        cellLoc='center',
        loc='center',
        cellColours=cell_colors,
        bbox=[0.0, 0.0, 1.0, 1.0],
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10.5)
    tbl.scale(1, 2.1)

    for j in range(len(col_headers)):
        cell = tbl[(0, j)]
        cell.set_facecolor(C_HEADER)
        cell.set_text_props(color=C_CYAN, fontweight='bold', fontsize=11)
        cell.set_edgecolor(C_BORDER)

    for i, (est, col) in enumerate(zip(estados, colores)):
        for j in range(len(col_headers)):
            cell = tbl[(i + 1, j)]
            cell.set_edgecolor(C_BORDER)
            if j in (3, 4):
                cell.set_text_props(color=col, fontweight='bold', fontsize=10.5)
            else:
                cell.set_text_props(color=C_TEXT, fontsize=10.5)

    # ── Barras horizontales (ancho completo) ──────────────────────────────────
    ax_bar = fig.add_subplot(gs[2])
    ax_bar.set_facecolor(C_PANEL)
    ax_bar.set_title("  Variación porcentual respecto al Escenario Base",
                     color=C_TEXT, fontsize=12, fontweight='bold', loc='left', pad=10)

    y    = np.arange(n)
    span = max(abs(c) for c in cambios_plot)
    bars = ax_bar.barh(y, cambios_plot, color=colores, edgecolor='none', height=0.5)

    label_offset = span * 0.015 + 0.4
    for bar, cambio, col in zip(bars, cambios_plot, colores):
        w  = bar.get_width()
        ha = 'left' if w >= 0 else 'right'
        xpos = w + label_offset if w >= 0 else w - label_offset
        ax_bar.text(xpos, bar.get_y() + bar.get_height() / 2,
                    f"{cambio:+.1f}%", va='center', ha=ha,
                    color=col, fontsize=10, fontweight='bold')

    ax_bar.axvline(0, color=C_BORDER, linewidth=1.5, linestyle='--')

    ax_bar.set_yticks(y)
    ax_bar.set_yticklabels([LABELS.get(m, m) for m in todas],
                            color=C_TEXT, fontsize=11, fontweight='bold')
    ax_bar.set_xlabel("Cambio porcentual (%)", color=C_MUTED, fontsize=10)
    ax_bar.tick_params(axis='x', colors=C_MUTED, labelsize=9.5, pad=5)
    ax_bar.tick_params(axis='y', length=0, pad=10)
    ax_bar.invert_yaxis()
    # Márgenes laterales para que las etiquetas no se corten
    ax_bar.set_xlim(-(span * 1.22), span * 1.22)

    for sp in ax_bar.spines.values():
        sp.set_color(C_BORDER)
    ax_bar.xaxis.grid(True, color=C_BORDER, linewidth=0.6, linestyle='--')
    ax_bar.set_axisbelow(True)

    leyenda = [
        mpatches.Patch(color=C_GREEN,  label="Mejora"),
        mpatches.Patch(color=C_RED,    label="Empeora"),
        mpatches.Patch(color=C_NEUTRO, label="Neutro"),
    ]
    ax_bar.legend(handles=leyenda, loc='lower right', framealpha=0.15,
                  facecolor=C_PANEL, edgecolor=C_BORDER,
                  labelcolor=C_TEXT, fontsize=10)

    # ── Tarjetas de resumen ───────────────────────────────────────────────────
    ax_sum = fig.add_subplot(gs[3])
    ax_sum.set_facecolor(C_BG)
    ax_sum.axis('off')

    tarjetas = [
        ("METRICAS MEJORADAS",  str(mejoras),      C_GREEN),
        ("METRICAS EMPEORADAS", str(empeoradas),    C_RED),
        ("TASA DE MEJORA",      f"{pct:.1f}%",      C_CYAN),
        ("TOTAL EVALUADAS",     str(len(todas)),    C_MUTED),
    ]

    box_w = 0.20
    gap   = (1.0 - len(tarjetas) * box_w) / (len(tarjetas) + 1)

    for idx, (label, valor, color) in enumerate(tarjetas):
        x0 = gap + idx * (box_w + gap)
        rect = mpatches.FancyBboxPatch(
            (x0, 0.08), box_w, 0.84,
            boxstyle="round,pad=0.02",
            facecolor=C_PANEL, edgecolor=color,
            linewidth=2.2,
            transform=ax_sum.transAxes, clip_on=False,
        )
        ax_sum.add_patch(rect)
        cx = x0 + box_w / 2
        ax_sum.text(cx, 0.63, valor, ha='center', va='center',
                    fontsize=30, fontweight='bold', color=color,
                    transform=ax_sum.transAxes)
        ax_sum.text(cx, 0.24, label, ha='center', va='center',
                    fontsize=8.5, color=C_MUTED,
                    transform=ax_sum.transAxes)

    plt.show()


# ── Entrada ───────────────────────────────────────────────────────────────────
def buscar_archivo(nombre: str) -> Path:
    directorio = Path(__file__).parent
    for ext in (".json", ".JSON"):
        ruta = directorio / f"{nombre}{ext}"
        if ruta.exists():
            return ruta
    raise FileNotFoundError(
        f"No se encontró '{nombre}.json' en {directorio}\n"
        f"  Coloca M1.json (base) y M2.json (nuevo) junto al script."
    )


def main():
    ruta_base  = buscar_archivo("M1")
    ruta_nueva = buscar_archivo("M2")
    print(f"  Base  → {ruta_base.name}")
    print(f"  Nuevo → {ruta_nueva.name}")
    base  = cargar_json(ruta_base)
    nuevo = cargar_json(ruta_nueva)
    mejoras, empeoradas = comparar_terminal(base, nuevo)
    mostrar_ventana(base, nuevo, mejoras, empeoradas)


if __name__ == "__main__":
    main()
