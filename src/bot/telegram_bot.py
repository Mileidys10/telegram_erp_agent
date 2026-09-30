"""Adaptador de comunicacion oficial con Telegram Bot API asincrono."""

import logging
import os
from typing import Optional
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from ..database.session import get_session
from .handlers import BotCommandHandler

logger = logging.getLogger("TelegramERPBot")


class TelegramERPBot:
    """Instancia del Bot de Telegram conectado a los servicios ERP y base de datos."""

    def __init__(self, token: str):
        self.token = token
        self.app: Application = ApplicationBuilder().token(self.token).build()
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Registra los manejadores de comandos y mensajes de texto."""
        # Comandos de autenticacion y consulta
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("vincular", self.cmd_link))
        self.app.add_handler(CommandHandler("stock", self.cmd_stock))
        self.app.add_handler(CommandHandler("kardex", self.cmd_kardex))
        self.app.add_handler(CommandHandler("alertas", self.cmd_alertas))

        # Comandos gerenciales de compras
        self.app.add_handler(CommandHandler("ordenes", self.cmd_ordenes))
        self.app.add_handler(CommandHandler("aprobar", self.cmd_aprobar))
        self.app.add_handler(CommandHandler("rechazar", self.cmd_rechazar))

        # Comandos de ventas y pedidos express
        self.app.add_handler(CommandHandler("pedido", self.cmd_pedido))
        self.app.add_handler(CommandHandler("confirmar_pedido", self.cmd_confirmar_pedido))

        # Comandos documentales de reportes PDF
        self.app.add_handler(CommandHandler("reporte", self.cmd_reporte))
        self.app.add_handler(CommandHandler("reporte_kardex", self.cmd_reporte_kardex))

        # Mensajes de texto libre con procesamiento semantico NLP
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.msg_nlp_router))

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Manejador /start."""
        user_id = update.effective_user.id
        with get_session() as session:
            text = BotCommandHandler.handle_start(user_id, session)
        await update.message.reply_text(text)

    async def cmd_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Manejador /vincular <OTP>."""
        user_id = update.effective_user.id
        otp = context.args[0] if context.args else ""
        with get_session() as session:
            text = BotCommandHandler.handle_link(user_id, otp, session)
        await update.message.reply_text(text)

    async def cmd_stock(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Manejador /stock <SKU o termino>."""
        user_id = update.effective_user.id
        query = " ".join(context.args) if context.args else ""
        with get_session() as session:
            text = BotCommandHandler.handle_stock(user_id, query, session)
        await update.message.reply_text(text)

    async def cmd_kardex(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Manejador /kardex <SKU>."""
        user_id = update.effective_user.id
        sku = context.args[0] if context.args else ""
        with get_session() as session:
            text = BotCommandHandler.handle_kardex(user_id, sku, session)
        await update.message.reply_text(text)

    async def cmd_alertas(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Manejador /alertas."""
        user_id = update.effective_user.id
        with get_session() as session:
            text = BotCommandHandler.handle_alertas(user_id, session)
        await update.message.reply_text(text)

    async def cmd_ordenes(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Manejador /ordenes."""
        user_id = update.effective_user.id
        with get_session() as session:
            text = BotCommandHandler.handle_ordenes_pendientes(user_id, session)
        await update.message.reply_text(text)

    async def cmd_aprobar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Manejador /aprobar <ID>."""
        user_id = update.effective_user.id
        order_id = int(context.args[0]) if (context.args and context.args[0].isdigit()) else 0
        with get_session() as session:
            text = BotCommandHandler.handle_aprobar_orden(user_id, order_id, session)
        await update.message.reply_text(text)

    async def cmd_rechazar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Manejador /rechazar <ID> <motivo>."""
        user_id = update.effective_user.id
        order_id = int(context.args[0]) if (context.args and context.args[0].isdigit()) else 0
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else ""
        with get_session() as session:
            text = BotCommandHandler.handle_rechazar_orden(user_id, order_id, reason, session)
        await update.message.reply_text(text)

    async def cmd_pedido(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Manejador /pedido <Cliente> <SKU> <Cantidad>."""
        user_id = update.effective_user.id
        if len(context.args) < 3:
            await update.message.reply_text("Uso: /pedido <NombreCliente> <SKU> <Cantidad>")
            return

        customer = context.args[0]
        sku = context.args[1]
        try:
            qty = float(context.args[2])
        except ValueError:
            await update.message.reply_text("Error: La cantidad debe ser un valor numerico.")
            return

        with get_session() as session:
            text = BotCommandHandler.handle_pedido(user_id, customer, sku, qty, session)
        await update.message.reply_text(text)

    async def cmd_confirmar_pedido(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Manejador /confirmar_pedido <ID_PEDIDO> <ID_BODEGA>."""
        user_id = update.effective_user.id
        if len(context.args) < 2 or not context.args[0].isdigit() or not context.args[1].isdigit():
            await update.message.reply_text("Uso: /confirmar_pedido <ID_PEDIDO> <ID_BODEGA>")
            return

        order_id = int(context.args[0])
        warehouse_id = int(context.args[1])
        with get_session() as session:
            text = BotCommandHandler.handle_confirmar_pedido(user_id, order_id, warehouse_id, session)
        await update.message.reply_text(text)

    async def cmd_reporte(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Manejador /reporte: Genera y envia el archivo PDF adjunto."""
        user_id = update.effective_user.id
        await update.message.reply_text("Generando informe de valorizacion de inventario...")
        with get_session() as session:
            msg, filepath = BotCommandHandler.handle_reporte(user_id, session)

        if filepath and os.path.exists(filepath):
            with open(filepath, "rb") as doc:
                await update.message.reply_document(document=doc, filename=os.path.basename(filepath), caption=msg)
        else:
            await update.message.reply_text(msg)

    async def cmd_reporte_kardex(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Manejador /reporte_kardex <SKU>: Genera y despacha la trazabilidad de Kardex en PDF."""
        user_id = update.effective_user.id
        sku = context.args[0] if context.args else ""
        if not sku:
            await update.message.reply_text("Uso: /reporte_kardex <SKU>")
            return

        await update.message.reply_text(f"Generando reporte de Kardex para {sku.upper()}...")
        with get_session() as session:
            msg, filepath = BotCommandHandler.handle_reporte_kardex(user_id, sku, session)

        if filepath and os.path.exists(filepath):
            with open(filepath, "rb") as doc:
                await update.message.reply_document(document=doc, filename=os.path.basename(filepath), caption=msg)
        else:
            await update.message.reply_text(msg)

    async def msg_nlp_router(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Enruta mensajes en lenguaje cotidiano con el analizador semantico NLP."""
        user_id = update.effective_user.id
        text = update.message.text
        with get_session() as session:
            response = BotCommandHandler.handle_free_text(user_id, text, session)
        await update.message.reply_text(response)

    def run_polling(self) -> None:
        """Inicia el bot en modo Polling asincrono continuo."""
        logger.info("Iniciando escucha de Telegram Bot API...")
        self.app.run_polling()
