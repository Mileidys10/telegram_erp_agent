# 🤖 Agente Autónomo de Telegram ERP

> Sistema de gestión de inventarios, alertas de stock mínimo y emisión automatizada de órdenes de compra en PDF a través de **Telegram Bot API**, gobernado por el estándar **Google Cloud OKF v0.2**.

---

## 🐳 Despliegue Rápido con Docker (Sin Instalar Dependencias)

Puedes ejecutar el bot de forma continua en cualquier servidor Linux, Windows o macOS con **Docker Compose**:

```bash
# 1. Clonar el repositorio
git clone https://github.com/Mileidys10/telegram_erp_agent.git
cd telegram_erp_agent

# 2. Configurar el token del bot en un archivo .env
echo "TELEGRAM_BOT_TOKEN=tu_token_aqui" > .env

# 3. Iniciar el contenedor en segundo plano
docker compose up --build -d

# 4. Ver logs en tiempo real
docker compose logs -f telegram-erp-agent
```

- 💾 **Persistencia:** La base de datos SQLite (`erp_inventory.db`) y las órdenes de compra en PDF (`./reports/`) se conservan de forma permanente en volúmenes locales.
- 🔄 **Reinicio Automático:** Configurado con `restart: unless-stopped` para tolerancia a fallos y reinicios del servidor.

---

## 🚀 Ejecución Local con Python (Alternativa)

Si prefieres ejecutar el proyecto directamente en tu entorno Python:

```bash
# Crear y activar entorno virtual
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno (.env)
cp .env.example .env

# Ejecutar el agente
python main.py
```

---

## 🛠️ Capacidades del Agente ERP

- **📦 Consulta de Stock en Tiempo Real:** Monitorización de niveles de inventario por almacén y SKU.
- **⚠️ Alertas Proactivas de Reabastecimiento:** Notificaciones automáticas cuando los productos caen por debajo del umbral de seguridad.
- **📄 Generación de Órdenes de Compra en PDF:** Maquetación automatizada con ReportLab Platypus.
- **🔐 Control de Acceso por Roles (RBAC):** Permisos diferenciados para administradores, operadores de bodega y compras.

---

## 📚 Tecnologías y Dependencias

- **Lenguaje:** Python 3.11+
- **Bot Framework:** `python-telegram-bot` v22
- **Persistencia:** `SQLAlchemy` 2.0 + SQLite ACID
- **Reportes:** `ReportLab` 4.0
- **Validación de Datos:** `Pydantic` v2
- **Arquitectura:** Clean Architecture, Servicios de Dominio & Testing Automatizado
