"""
Módulo de conexión a Azure SQL Database.
Lee la cadena de conexión desde .env (variable DB_CONNECTION_STRING).
"""
import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

_connection_string: str = os.getenv("DB_CONNECTION_STRING", "")


def get_connection() -> pyodbc.Connection:
    """Abre y devuelve una conexión ODBC a Azure SQL."""
    if not _connection_string:
        raise RuntimeError(
            "DB_CONNECTION_STRING no está definida. "
            "Revisa tu archivo .env en la raíz del proyecto."
        )
    return pyodbc.connect(_connection_string)


def init_schema() -> None:
    """
    Crea las tablas si no existen.
    Llamar una vez al arrancar la app o desde un script de migración.
    """
    ddl = """
    -- Tabla de usuarios
    IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'users')
    CREATE TABLE users (
        user_id         INT IDENTITY(1,1) PRIMARY KEY,
        username        NVARCHAR(100)   NOT NULL UNIQUE,
        password_hash   NVARCHAR(256)   NOT NULL,
        created_at      DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME()
    );

    -- Tabla de robots registrados
    IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'robots')
    CREATE TABLE robots (
        robot_id    INT IDENTITY(1,1) PRIMARY KEY,
        nombre      NVARCHAR(100)   NOT NULL,
        escenario   NVARCHAR(100)   NOT NULL,
        spawn_x     INT             NOT NULL,
        spawn_y     INT             NOT NULL,
        activo      BIT             NOT NULL DEFAULT 1,
        user_id     INT             NULL REFERENCES users(user_id)
    );

    -- Tabla de pedidos
    IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'pedidos')
    CREATE TABLE pedidos (
        pedido_id       INT             NOT NULL,
        anaquel_id      INT             NOT NULL,
        estacion_id     INT             NOT NULL,
        tick_creacion   INT             NOT NULL DEFAULT 0,
        escenario       NVARCHAR(100)   NOT NULL,
        seed            INT             NOT NULL,
        PRIMARY KEY (escenario, seed, pedido_id)
    );

    -- Tabla de corridas (runs) con métricas
    IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'runs')
    CREATE TABLE runs (
        run_id                          INT IDENTITY(1,1) PRIMARY KEY,
        escenario                       NVARCHAR(100)   NOT NULL,
        seed                            INT             NOT NULL,
        num_robots                      INT             NOT NULL,
        ticks                           INT             NOT NULL,
        fecha                           DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),
        pedidos_totales                 INT,
        pedidos_completados             INT,
        tiempo_promedio_pedido_ticks    FLOAT,
        throughput_pedidos_por_1000t    FLOAT,
        tiempo_promedio_espera_ticks    FLOAT,
        utilizacion_promedio            FLOAT,
        colisiones_vertice              INT,
        intercambios_arista             INT,
        deadlock                        INT,
        eventos_alto                    INT,
        distancia_total_celdas          INT,
        user_id                         INT NULL REFERENCES users(user_id)
    );

    -- Agregar user_id a tablas existentes si no existe
    IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('robots') AND name = 'user_id')
        ALTER TABLE robots ADD user_id INT NULL REFERENCES users(user_id);

    IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('runs') AND name = 'user_id')
        ALTER TABLE runs ADD user_id INT NULL REFERENCES users(user_id);
    """
    conn = get_connection()
    try:
        conn.execute(ddl)
        conn.commit()
    finally:
        conn.close()
