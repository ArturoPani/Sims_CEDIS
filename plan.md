# Plan: Aplicación Web Operativa del CEDIS

## Arquitectura
Browser  ←─polling─→  FastAPI (Azure App Service)
                          ├── SimAlmacen (hilo de fondo)
                          ├── Azure SQL (robots, pedidos, runs)
                          └── outputs/ (layout.npy, JSONs estáticos)

## Pasos

### [x] 1. Estructura base de FastAPI
Crear carpeta `api/` con `api/main.py` como entry point.
Mantener todos los módulos existentes intactos — la API los importa.

### [x] 2. Capa de BD — `db/connection.py` y `db/crud.py`
Tablas en Azure SQL:
- `robots`  → robot_id, nombre, escenario, spawn_x, spawn_y, activo
- `pedidos` → pedido_id, anaquel_id, estacion_id, tick_creacion, escenario, seed
- `runs`    → run_id, escenario, seed, num_robots, ticks, fecha, + todas las métricas

### [x] 3. Router de robots — `api/routers/robots.py`
- GET  /robots          → listar robots registrados
- POST /robots          → dar de alta un robot (guarda en BD)
- DELETE /robots/{id}   → dar de baja

### [x] 4. Router de pedidos — `api/routers/pedidos.py`
- GET  /pedidos          → ver pedidos del escenario activo
- POST /pedidos/generar  → invocar generador_pedidos.py y guardar en BD
- GET  /pedidos/{id}     → estado de un pedido (pendiente/completado/en proceso)

### [x] 5. Router de simulación — `api/routers/simulacion.py`
- POST /simulacion/iniciar  → lanza SimAlmacen en hilo de fondo
- POST /simulacion/detener
- GET  /simulacion/estado   → polling: tick actual + por robot:
                              {robot_id, pos_x, pos_y, estado, pedido_id,
                               ticks_restantes, eta_seg}
- GET  /simulacion/metricas → métricas parciales o finales

### [x] 6. Sim runner — `api/sim_runner.py`
Wrapper con estado thread-safe de SimAlmacen.
Calcula por robot: ticks_restantes = len(ruta) - idx_ruta
                   eta_seg = ticks_restantes × segundos_por_tick (configurable)

### [x] 7. Frontend — `frontend/index.html`
- Panel izq: registrar robots, generar pedidos, iniciar/detener
- Panel der: canvas del grid con robots como puntos de colores
             tooltip al hover: ETA y destino actual
- Tabla inferior: pedidos con estado en tiempo real
- Columna ETA en tabla de robots: "--" | "En destino" | "~Xs"
- Polling cada 2 segundos a /simulacion/estado

### [ ] 8. Configuración — `.env` + `.gitignore`
python-dotenv para connection string Azure SQL y config general.

### [ ] 9. Dependencias — `requirements.txt`
Agregar: fastapi, uvicorn, pyodbc, python-dotenv

### [ ] 10. Deploy — Azure App Service
Procfile o startup.sh con: uvicorn api.main:app
Layout estático y JSONs van como archivos del App Service.

## Verificación final
1. uvicorn api.main:app --reload  (local)
2. POST /robots  ×5
3. POST /pedidos/generar
4. POST /simulacion/iniciar → ver robots moviéndose en canvas
5. GET  /simulacion/metricas → verificar guardado en tabla runs

## Decisiones
- FastAPI + HTML/JS vanilla (sin React): menor overhead, suficiente para scope académico
- Polling c/2s (sin WebSocket): más simple, suficiente dado que 1 tick no es sub-segundo
- Sim en memoria, BD solo persiste config y resultados (no estado tick a tick)
- Anaqueles/spawns/layout permanecen en disco (migrarlos a SQL añade latencia sin beneficio)