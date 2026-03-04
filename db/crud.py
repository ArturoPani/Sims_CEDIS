"""
Operaciones CRUD contra Azure SQL para robots, pedidos y runs.
"""
from typing import Dict, List, Optional, Tuple
from db.connection import get_connection


# ═══════════════════════════════════════════════════════════════
#  ROBOTS
# ═══════════════════════════════════════════════════════════════

def insertar_robot(nombre: str, escenario: str, spawn_x: int, spawn_y: int) -> int:
    """Da de alta un robot y devuelve su robot_id generado."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO robots (nombre, escenario, spawn_x, spawn_y, activo)
            OUTPUT INSERTED.robot_id
            VALUES (?, ?, ?, ?, 1)
            """,
            (nombre, escenario, spawn_x, spawn_y),
        )
        robot_id = cursor.fetchone()[0]
        conn.commit()
        return robot_id
    finally:
        conn.close()


def listar_robots(escenario: str, solo_activos: bool = True) -> List[Dict]:
    """Devuelve lista de robots registrados para un escenario."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = "SELECT robot_id, nombre, escenario, spawn_x, spawn_y, activo FROM robots WHERE escenario = ?"
        if solo_activos:
            query += " AND activo = 1"
        query += " ORDER BY robot_id"
        cursor.execute(query, (escenario,))
        cols = [desc[0] for desc in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def desactivar_robot(robot_id: int) -> bool:
    """Desactiva (baja lógica) un robot. Devuelve True si existía."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE robots SET activo = 0 WHERE robot_id = ?", (robot_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def obtener_spawns_de_robots(escenario: str) -> List[Tuple[int, int]]:
    """Devuelve los puntos de spawn de los robots activos, en orden de robot_id."""
    robots = listar_robots(escenario, solo_activos=True)
    return [(r["spawn_x"], r["spawn_y"]) for r in robots]


# ═══════════════════════════════════════════════════════════════
#  PEDIDOS
# ═══════════════════════════════════════════════════════════════

def insertar_pedidos(pedidos: List[Dict], escenario: str, seed: int) -> int:
    """
    Inserta un lote de pedidos. Cada dict debe tener:
      pedido_id, anaquel_id, estacion_id, tick_creacion
    Devuelve la cantidad de filas insertadas.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.fast_executemany = True
        rows = [
            (p["pedido_id"], p["anaquel_id"], p["estacion_id"],
             p.get("tick_creacion", 0), escenario, seed)
            for p in pedidos
        ]
        cursor.executemany(
            """
            INSERT INTO pedidos (pedido_id, anaquel_id, estacion_id, tick_creacion, escenario, seed)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def listar_pedidos(escenario: str, seed: Optional[int] = None) -> List[Dict]:
    """Devuelve pedidos de un escenario (opcionalmente filtrados por seed)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = "SELECT pedido_id, anaquel_id, estacion_id, tick_creacion, escenario, seed FROM pedidos WHERE escenario = ?"
        params: list = [escenario]
        if seed is not None:
            query += " AND seed = ?"
            params.append(seed)
        query += " ORDER BY pedido_id"
        cursor.execute(query, params)
        cols = [desc[0] for desc in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def eliminar_pedidos(escenario: str, seed: Optional[int] = None) -> int:
    """Elimina pedidos de un escenario (opcionalmente solo de un seed). Devuelve filas borradas."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = "DELETE FROM pedidos WHERE escenario = ?"
        params: list = [escenario]
        if seed is not None:
            query += " AND seed = ?"
            params.append(seed)
        cursor.execute(query, params)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
#  RUNS (métricas)
# ═══════════════════════════════════════════════════════════════

def guardar_run(escenario: str, metricas: Dict) -> int:
    """
    Guarda una corrida con sus métricas. Espera el dict que devuelve SimAlmacen.metricas().
    Devuelve el run_id generado.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO runs (
                escenario, seed, num_robots, ticks,
                pedidos_totales, pedidos_completados,
                tiempo_promedio_pedido_ticks, throughput_pedidos_por_1000t,
                tiempo_promedio_espera_ticks, utilizacion_promedio,
                colisiones_vertice, intercambios_arista,
                deadlock, eventos_alto, distancia_total_celdas
            )
            OUTPUT INSERTED.run_id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                escenario,
                metricas.get("seed"),
                metricas.get("robots"),
                metricas.get("tick_final"),
                metricas.get("pedidos_totales"),
                metricas.get("pedidos_completados"),
                metricas.get("tiempo_promedio_pedido_ticks"),
                metricas.get("throughput_pedidos_por_1000_ticks"),
                metricas.get("tiempo_promedio_espera_ticks"),
                metricas.get("utilizacion_promedio"),
                metricas.get("colisiones_vertice"),
                metricas.get("intercambios_arista"),
                metricas.get("deadlock"),
                metricas.get("eventos_alto"),
                metricas.get("distancia_total_celdas"),
            ),
        )
        run_id = cursor.fetchone()[0]
        conn.commit()
        return run_id
    finally:
        conn.close()


def listar_runs(escenario: Optional[str] = None) -> List[Dict]:
    """Devuelve historial de corridas, opcionalmente filtrado por escenario."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
            SELECT run_id, escenario, seed, num_robots, ticks, fecha,
                   pedidos_totales, pedidos_completados,
                   tiempo_promedio_pedido_ticks, throughput_pedidos_por_1000t,
                   tiempo_promedio_espera_ticks, utilizacion_promedio,
                   colisiones_vertice, intercambios_arista,
                   deadlock, eventos_alto, distancia_total_celdas
            FROM runs
        """
        params: list = []
        if escenario:
            query += " WHERE escenario = ?"
            params.append(escenario)
        query += " ORDER BY fecha DESC"
        cursor.execute(query, params)
        cols = [desc[0] for desc in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]
    finally:
        conn.close()
