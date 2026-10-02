# ==============================================================================
# Dockerfile — Agente Autónomo de Telegram ERP
# Telegram ERP Agent - Contenedorización Docker
# ==============================================================================

FROM python:3.11-slim

LABEL maintainer="Mileidys10 <agamezmileidys@gmail.com>"
LABEL project="Telegram ERP Agent"
LABEL version="1.0.0"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Instalar utilidades de sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente
COPY src/ ./src/
COPY erp_inventory.db .
COPY main.py .

# Crear directorio para almacenar reportes PDF
RUN mkdir -p /app/reports

# Comando por defecto para iniciar el daemon del bot
CMD ["python", "main.py"]
