"""Demonio de monitoreo continuo de niveles de stock critico y emision de alertas."""

from datetime import datetime, timezone
import logging
import threading
import time
from typing import Callable, Dict, List, Optional
from sqlalchemy.orm import Session

from ..database.session import get_session
from ..domain.models import AuditLog, Product, Stock, User, UserRole, utc_now
from .inventory_service import InventoryService

logger = logging.getLogger("AlertMonitor")


class AlertMonitorDaemon:
    """Servicio de monitoreo proactivo de inventario contra umbrales minimos."""

    def __init__(self, interval_seconds: int = 300):
        self.interval_seconds = interval_seconds
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @staticmethod
    def inspect_critical_stock(session: Session) -> List[Dict]:
        """Audita la base de datos y retorna productos en quiebre o riesgo de desabastecimiento."""
        critical_items = InventoryService.get_critical_stock_items(session)
        alerts = []
        for item in critical_items:
            alerts.append({
                "sku": item["sku"],
                "name": item["name"],
                "current_stock": item["current_stock"],
                "stock_minimo": item["stock_minimo"],
                "deficit": item["deficit"],
                "unit": item["unit_measure"],
                "timestamp": utc_now(),
            })
        return alerts

    def run_check_cycle(self, on_alert_found: Optional[Callable[[List[Dict]], None]] = None) -> List[Dict]:
        """Ejecuta una pasada de verificacion y notifica a los destinatarios autorizados."""
        with get_session() as session:
            alerts = self.inspect_critical_stock(session)
            if alerts:
                # Registrar auditoria del evento de monitoreo
                skus = ", ".join([a["sku"] for a in alerts[:5]])
                audit = AuditLog(
                    telegram_user_id=None,
                    action="MONITOR_ALERTA_STOCK",
                    details=f"Deteccion de {len(alerts)} articulos bajo minimo: {skus}",
                )
                session.add(audit)
                session.commit()

                if on_alert_found:
                    on_alert_found(alerts)

            return alerts

    def start(self, on_alert_found: Optional[Callable[[List[Dict]], None]] = None) -> None:
        """Inicia el hilo de monitoreo continuo en segundo plano."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()

        def _worker():
            logger.info("Iniciando bucle de monitoreo de stock...")
            while not self._stop_event.is_set():
                try:
                    self.run_check_cycle(on_alert_found)
                except Exception as e:
                    logger.error(f"Error en ciclo de monitoreo: {e}")
                self._stop_event.wait(self.interval_seconds)

        self._thread = threading.Thread(target=_worker, daemon=True, name="StockMonitorThread")
        self._thread.start()

    def stop(self) -> None:
        """Detiene el demonio de monitoreo de forma limpia."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
