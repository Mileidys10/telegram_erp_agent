# ==============================================================================
# Dockerfile — Agente Autónomo de Telegram ERP
# ==============================================================================

FROM python:3.11-slim

LABEL maintainer="Mileidys10 <agamezmileidys@gmail.com>"
LABEL project="Telegram ERP Agent"
LABEL version="1.1.0"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no root
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY erp_inventory.db .
COPY main.py .

RUN mkdir -p /app/reports && \
    chown -R appuser:appgroup /app

USER appuser

CMD ["python", "main.py"]
