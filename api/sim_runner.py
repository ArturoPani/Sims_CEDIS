"""
Wrapper thread-safe que mantiene una instancia de SimAlmacen en memoria
y permite consultarla desde los endpoints de FastAPI.
"""
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import numpy as np
import os

from sim_core import Pedido, SimAlmacen, SimConfig, cargar_layout


@dataclass
class EstadoRobot:
    robot_id: int
    pos_x: int
    pos_y: int
    estado: str
    pedido_id: Optional[int]
    ticks_restantes: int
    eta_seg: float


class SimRunner:
    """Singleton que gestiona la simulación activa."""

    def __init__(self):
        self._sim: Optional[SimAlmacen] = None
        self._hilo: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._corriendo = False
        self._detenido = threading.Event()
        self._ticks_objetivo = 0
        self._seg_por_tick = 0.05  # configurable
        self._escenario: str = ""
        self._finalizado = False
        self._visitas: Optional[np.ndarray] = None
        self._esperas: Optional[np.ndarray] = None
        self._grid: Optional[np.ndarray] = None

    # ── Estado público ───────────────────────────────────────────

    @property
    def activo(self) -> bool:
        return self._corriendo

    @property
    def finalizado(self) -> bool:
        return self._finalizado

    @property
    def escenario(self) -> str:
        return self._escenario

    # ── Iniciar simulación ───────────────────────────────────────

    def iniciar(
        self,
        escenario: str,
        seed: int,
        ticks: int,
        pedidos: List[Pedido],
        puntos_spawn: List[tuple],
        num_robots: int,
        seg_por_tick: float = 0.05,
        movimientos_permitidos=None,
        costos_direccion=None,
        celdas_no_stop=None,
        config: Optional["SimConfig"] = None,
    ) -> None:
        if self._corriendo:
            raise RuntimeError("Ya hay una simulación en curso.")

        grid, estacion_dock, anaquel_home, _ = cargar_layout(
            f"outputs/{escenario}/layout.npy",
            f"outputs/{escenario}/estaciones.json",
            f"outputs/{escenario}/anaqueles.json",
            f"outputs/{escenario}/spawn.json",
        )

        alto, ancho = grid.shape
        self._grid = grid
        self._visitas = np.zeros((alto, ancho), dtype=np.int32)
        self._esperas = np.zeros((alto, ancho), dtype=np.int32)

        sim = SimAlmacen(
            grid=grid,
            estacion_dock=estacion_dock,
            anaquel_home=anaquel_home,
            robots=num_robots,
            puntos_spawn=puntos_spawn,
            pedidos=pedidos,
            seed=seed,
            movimientos_permitidos=movimientos_permitidos,
            costos_direccion=costos_direccion,
            celdas_no_stop=celdas_no_stop,
            config=config,
        )

        with self._lock:
            self._sim = sim
            self._ticks_objetivo = ticks
            self._seg_por_tick = seg_por_tick
            self._escenario = escenario
            self._corriendo = True
            self._finalizado = False
            self._detenido.clear()

        self._hilo = threading.Thread(target=self._loop, daemon=True)
        self._hilo.start()

    # ── Loop interno (corre en hilo separado) ────────────────────

    def _loop(self) -> None:
        try:
            while not self._detenido.is_set():
                with self._lock:
                    if self._sim is None:
                        break
                    if self._sim.tick >= self._ticks_objetivo:
                        break
                    self._sim.step()
                    if self._visitas is not None:
                        for r in self._sim.lista_robots:
                            x, y = r.pos
                            self._visitas[y, x] += 1
                            if r.estado == "esperando":
                                self._esperas[y, x] += 1
                time.sleep(self._seg_por_tick)
        finally:
            with self._lock:
                self._corriendo = False
                self._finalizado = True

    # ── Detener ──────────────────────────────────────────────────

    def detener(self) -> None:
        self._detenido.set()
        if self._hilo and self._hilo.is_alive():
            self._hilo.join(timeout=5)
        with self._lock:
            self._corriendo = False

    # ── Consultar estado (thread-safe) ───────────────────────────

    def estado(self) -> Dict[str, Any]:
        with self._lock:
            if self._sim is None:
                return {"activo": False, "tick": 0, "robots": []}

            robots_estado: List[Dict] = []
            for r in self._sim.lista_robots:
                ticks_rest = max(0, len(r.ruta) - r.idx_ruta - 1) if r.ruta else 0
                robots_estado.append({
                    "robot_id": r.robot_id,
                    "pos_x": r.pos[0],
                    "pos_y": r.pos[1],
                    "estado": r.estado,
                    "pedido_id": r.pedido_id,
                    "ticks_restantes": ticks_rest,
                    "eta_seg": round(ticks_rest * self._seg_por_tick, 2),
                })

            pedidos_estado: List[Dict] = []
            for p in self._sim.pedidos:
                if p.tick_completado is not None:
                    st = "completado"
                elif p.tick_asignacion is not None:
                    st = "en_proceso"
                elif p.tick_creacion <= self._sim.tick:
                    st = "pendiente"
                else:
                    st = "no_liberado"
                pedidos_estado.append({
                    "pedido_id": p.pedido_id,
                    "anaquel_id": p.anaquel_id,
                    "estacion_id": p.estacion_id,
                    "estado": st,
                })

            return {
                "activo": self._corriendo,
                "finalizado": self._finalizado,
                "escenario": self._escenario,
                "tick": self._sim.tick,
                "ticks_objetivo": self._ticks_objetivo,
                "progreso_pct": round(100 * self._sim.tick / max(1, self._ticks_objetivo), 1),
                "robots": robots_estado,
                "pedidos": pedidos_estado,
            }

    # ── Métricas (parciales o finales) ───────────────────────────

    def metricas(self) -> Optional[Dict]:
        with self._lock:
            if self._sim is None:
                return None
            return self._sim.metricas()

    def generar_heatmaps(self, run_id: int) -> bool:
        """Genera y guarda los 3 heatmaps para el run dado. Devuelve True si OK."""
        with self._lock:
            if self._grid is None or self._visitas is None or self._esperas is None:
                return False
            grid = self._grid.copy()
            visitas = self._visitas.copy()
            esperas = self._esperas.copy()

        try:
            from visualiza_simulacion import guardar_heatmaps
            carpeta = os.path.join("outputs", "runs", str(run_id))
            os.makedirs(carpeta, exist_ok=True)
            prefijo = os.path.join(carpeta, "heatmap")
            guardar_heatmaps(grid, visitas, esperas, prefijo=prefijo)
            return True
        except Exception:
            return False


# Instancia global (singleton)
runner = SimRunner()
