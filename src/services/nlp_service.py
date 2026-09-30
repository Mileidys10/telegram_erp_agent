"""Servicio de procesamiento de lenguaje natural (NLP) con Google Gemini y fallback semantico."""

import logging
import os
import re
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("NLPService")


class NLPService:
    """Clasificador de intenciones conversacionales para operaciones de inventario y ERP."""

    INTENT_STOCK = "STOCK"
    INTENT_KARDEX = "KARDEX"
    INTENT_PENDING_ORDERS = "PENDING_ORDERS"
    INTENT_CRITICAL_STOCK = "CRITICAL_STOCK"
    INTENT_REPORT = "REPORT"
    INTENT_SALES_QUOTE = "SALES_QUOTE"
    INTENT_HELP = "HELP"
    INTENT_UNKNOWN = "UNKNOWN"

    @classmethod
    def parse_intent(cls, message_text: str) -> Tuple[str, Optional[str]]:
        """Analiza el mensaje en lenguaje natural. Utiliza Gemini AI si la API Key esta configurada,

        o el motor determinista semantico de alta precision como fallback local.
        """
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            try:
                intent, param = cls._parse_intent_with_gemini(message_text, api_key)
                if intent != cls.INTENT_UNKNOWN:
                    return intent, param
            except Exception as e:
                logger.warning(f"Error al invocar Google Gemini API, utilizando fallback local: {e}")

        return cls._parse_intent_local(message_text)

    @classmethod
    def _parse_intent_local(cls, message_text: str) -> Tuple[str, Optional[str]]:
        """Motor semantico local basado en analisis lexico y patrones regulares en español."""
        text = message_text.strip().lower()

        # 1. Intencion: Reporte PDF
        if any(w in text for w in ("reporte", "informe", "pdf", "valorizacion", "balance de stock")):
            return cls.INTENT_REPORT, None

        # 2. Intencion: Stock Critico / Alertas
        if any(w in text for w in ("critico", "quiebre", "bajo minimo", "reorden", "por agotarse", "alertas")):
            return cls.INTENT_CRITICAL_STOCK, None

        # 3. Intencion: Ordenes de Compra Pendientes
        if any(w in text for w in ("ordenes pendientes", "ordenes de compra", "compras por aprobar", "aprobar compra")):
            return cls.INTENT_PENDING_ORDERS, None

        # 4. Intencion: Cotizacion de Venta / Pedido Express
        if any(w in text for w in ("cotizar", "cotizacion", "nuevo pedido", "hacer pedido", "vender")):
            match = re.search(r"(?:cotizar|pedido|vender)\s+(?:de\s+)?([a-zA-Z0-9\-_]+)", text)
            sku = match.group(1) if match else None
            return cls.INTENT_SALES_QUOTE, sku

        # 5. Intencion: Kardex / Historial de Movimientos
        if "kardex" in text or "movimientos" in text or "historial de" in text:
            match = re.search(r"(?:kardex|movimientos|historial)\s+(?:de\s+)?([a-zA-Z0-9\-_]+)", text)
            sku = match.group(1) if match else None
            return cls.INTENT_KARDEX, sku

        # 6. Intencion: Consulta de Stock
        stock_patterns = [
            r"(?:cuanto|cuantos|cuantas|stock|hay|queda|quedan|existencia|existencias|disponible)\s+(?:nos\s+queda\s+|nos\s+quedan\s+|queda\s+|quedan\s+|hay\s+|unidades\s+hay\s+)?(?:de\s+|del\s+)?([a-zA-Z0-9\-_]+)",
            r"stock\s+([a-zA-Z0-9\-_]+)",
        ]
        for pat in stock_patterns:
            m = re.search(pat, text)
            if m:
                target = m.group(1).strip()
                if target not in ("stock", "inventario", "el", "la", "los", "las", "un", "una"):
                    return cls.INTENT_STOCK, target

        # 7. Intencion: Ayuda
        if any(w in text for w in ("ayuda", "comandos", "que puedes hacer", "manual", "opciones")):
            return cls.INTENT_HELP, None

        return cls.INTENT_UNKNOWN, None

    @classmethod
    def _parse_intent_with_gemini(cls, message_text: str, api_key: str) -> Tuple[str, Optional[str]]:
        """Clasificacion estructurada mediante Google Gemini con Tool / Function Calling."""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        prompt = f"""
        Actua como el clasificador de intenciones del ERP.
        Mensaje del usuario: "{message_text}"

        Clasifica la intencion seleccionando exactamente una de las siguientes:
        - STOCK: Si pregunta por cantidad, disponibilidad o precio de un producto. Parametro: el SKU o nombre buscado.
        - KARDEX: Si solicita ver movimientos o historial de entradas/salidas de un producto. Parametro: el SKU o nombre.
        - CRITICAL_STOCK: Si pregunta por productos que se estan agotando, alertas o stock minimo.
        - PENDING_ORDERS: Si pregunta por ordenes de compra pendientes de aprobacion.
        - REPORT: Si pide generar o descargar un reporte PDF o informe de inventario.
        - SALES_QUOTE: Si solicita crear un pedido, cotizacion o venta.
        - HELP: Si pide ayuda o instrucciones.
        - UNKNOWN: Si no tiene relacion con el ERP.

        Responde unicamente en formato JSON:
        {{"intent": "...", "param": "..."}}
        """

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

        import json
        data = json.loads(response.text)
        intent = data.get("intent", cls.INTENT_UNKNOWN).upper()
        param = data.get("param")
        if param == "null" or param == "":
            param = None

        return intent, param
