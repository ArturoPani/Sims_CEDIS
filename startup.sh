#!/bin/bash
set -e

# â”€â”€ Instalar ODBC Driver 18 (necesario para pyodbc â†’ Azure SQL) â”€â”€
if ! odbcinst -q -d 2>/dev/null | grep -qi "ODBC Driver 18"; then
  echo "[startup] Instalando ODBC Driver 18..."
  curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg
  echo "deb [signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list
  apt-get update -qq
  ACCEPT_EULA=Y apt-get install -y -qq msodbcsql18 unixodbc-dev
  echo "[startup] ODBC Driver 18 instalado."
else
  echo "[startup] ODBC Driver 18 ya presente."
fi

# â”€â”€ Instalar dependencias Python si faltan â”€â”€
pip install -r requirements.txt --quiet 2>/dev/null || true

# â”€â”€ Arrancar gunicorn â”€â”€
echo "[startup] Iniciando gunicorn en puerto ${PORT:-8000}..."
gunicorn api.main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers 2 \
  --bind 0.0.0.0:${PORT:-8000} \
  --timeout 120
