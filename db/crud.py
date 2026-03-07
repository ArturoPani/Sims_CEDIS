"""Operaciones CRUD contra Azure SQL para usuarios, robots, pedidos y runs."""
import hashlib
import os
from typing import Dict, List, Optional, Tuple
from db.connection import get_connection


# ═══════════════════════════════════════════════════════════════
#  USUARIOS
# ═══════════════════════════════════════════════════════════════

def _hash_password(password: str, salt: bytes | None = None) -> str:
    """Hash con PBKDF2-SHA256 + salt aleatorio. Devuelve 'salt_hex:hash_hex'."""
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations=260_000)
    return salt.hex() + ":" + dk.hex()


def _verify_password(password: str, stored: str) -> bool:
    salt_hex, _ = stored.split(":", 1)
    return _hash_password(password, bytes.fromhex(salt_hex)) == stored


def crear_usuario(username: str, password: str) -> int:
    """Crea un usuario y devuelve su user_id."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO users (username, password_hash)
            OUTPUT INSERTED.user_id
            VALUES (?, ?)
            """,
            (username, _hash_password(password)),
        )
        user_id = cursor.fetchone()[0]
        conn.commit()
        return user_id
    finally:
        conn.close()


def buscar_usuario(username: str) -> Optional[Dict]:
    """Busca un usuario por nombre. Devuelve dict con user_id, username, password_hash o None."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, username, password_hash FROM users WHERE username = ?",
            (username,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        cols = [desc[0] for desc in cursor.description]
        return dict(zip(cols, row))
    finally:
        conn.close()


def autenticar_usuario(username: str, password: str) -> Optional[Dict]:
    """Valida credenciales. Devuelve {user_id, username} si ok, None si no."""
    user = buscar_usuario(username)
    if user is None:
        return None
    if not _verify_password(password, user["password_hash"]):
        return None
    return {"user_id": user["user_id"], "username": user["username"]}


def listar_usuarios() -> List[Dict]:
    """Devuelve todos los usuarios (sin password_hash)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, created_at FROM users ORDER BY user_id")
    rows = cursor.fetchall()
    conn.close()
    return [{"user_id": r[0], "username": r[1], "created_at": str(r[2])} for r in rows]


# ═══════════════════════════════════════════════════════════════
#  ROBOTS
# ═══════════════════════════════════════════════════════════════

def insertar_robot(nombre: str, escenario: str, spawn_x: int, spawn_y: int, user_id: Optional[int] = None) -> int:
    """Da de alta un robot y devuelve su robot_id generado."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO robots (nombre, escenario, spawn_x, spawn_y, activo, user_id)
            OUTPUT INSERTED.robot_id
            VALUES (?, ?, ?, ?, 1, ?)
            """,
            (nombre, escenario, spawn_x, spawn_y, user_id),
        )
        robot_id = cursor.fetchone()[0]
        conn.commit()
        return robot_id
    finally:
        conn.close()


def listar_robots(escenario: str, solo_activos: bool = True, user_id: Optional[int] = None) -> List[Dict]:
    """Devuelve lista de robots registrados para un escenario, filtrados por usuario."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = "SELECT robot_id, nombre, escenario, spawn_x, spawn_y, activo FROM robots WHERE escenario = ?"
        params: list = [escenario]
        if solo_activos:
            query += " AND activo = 1"
        if user_id is not None:
            query += " AND user_id = ?"
            params.append(user_id)
        query += " ORDER BY robot_id"
        cursor.execute(query, params)
        cols = [desc[0] for desc in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def desactivar_robot(robot_id: int, user_id: Optional[int] = None) -> bool:
    """Desactiva (baja lógica) un robot. Solo si pertenece al usuario."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = "UPDATE robots SET activo = 0 WHERE robot_id = ?"
        params: list = [robot_id]
        if user_id is not None:
            query += " AND user_id = ?"
            params.append(user_id)
        cursor.execute(query, params)
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def obtener_spawns_de_robots(escenario: str, user_id: Optional[int] = None) -> List[Tuple[int, int]]:
    """Devuelve los puntos de spawn de los robots activos, en orden de robot_id."""
    robots = listar_robots(escenario, solo_activos=True, user_id=user_id)
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

def guardar_run(escenario: str, metricas: Dict, user_id: Optional[int] = None) -> int:
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
                deadlock, eventos_alto, distancia_total_celdas, relevos,
                user_id
            )
            OUTPUT INSERTED.run_id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                metricas.get("relevos", 0),
                user_id,
            ),
        )
        run_id = cursor.fetchone()[0]
        conn.commit()
        return run_id
    finally:
        conn.close()


def listar_runs(escenario: Optional[str] = None, user_id: Optional[int] = None) -> List[Dict]:
    """Devuelve historial de corridas, filtrado por escenario y/o usuario."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
            SELECT run_id, escenario, seed, num_robots, ticks, fecha,
                   pedidos_totales, pedidos_completados,
                   tiempo_promedio_pedido_ticks, throughput_pedidos_por_1000t,
                   tiempo_promedio_espera_ticks, utilizacion_promedio,
                   colisiones_vertice, intercambios_arista,
                   deadlock, eventos_alto, distancia_total_celdas, relevos
            FROM runs
        """
        clauses: list = []
        params: list = []
        if escenario:
            clauses.append("escenario = ?")
            params.append(escenario)
        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(user_id)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY fecha DESC"
        cursor.execute(query, params)
        cols = [desc[0] for desc in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]
    finally:
        conn.close()
