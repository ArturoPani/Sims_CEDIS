#!/bin/bash
# Startup script para Azure App Service (Linux)
# Configura: App Service → Configuration → General settings → Startup Command:
#   bash startup.sh

gunicorn api.main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers 2 \
  --bind 0.0.0.0:${PORT:-8000} \
  --timeout 120
