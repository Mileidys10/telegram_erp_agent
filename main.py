"""Punto de entrada principal para el Agente de Telegram ERP."""

import argparse
import os
import sys
from typing import Optional

from src.bot.handlers import BotCommandHandler
from src.database.session import get_session, init_db
from src.domain.models import Product, PurchaseOrder, Stock, User, UserRole, Warehouse
from src.services.alert_monitor import AlertMonitorDaemon
from src.services.auth_service import AuthService


def seed_demo_data(session) -> None:
    """Inserta datos iniciales de demostracion si la base de datos esta vacia."""
    if session.query(Warehouse).first():
        return

    print("[INFO] Inicializando datos demo de inventario y ERP...")

    # 1. Almacenes
    w_main = Warehouse(code="BOD-01", name="Bodega Central Santiago", location="Av. Industrial 450")
    w_sec = Warehouse(code="BOD-02", name="Bodega Sucursal Norte", location="Ruta 5 Norte Km 12")
    session.add_all([w_main, w_sec])
    session.flush()

    # 2. Usuarios
    admin = User(
        username="admin",
        full_name="Carlos Administrador",
        email="admin@empresa.com",
        role=UserRole.ADMIN.value,
        telegram_user_id=1001,
        is_active=True,
    )
    gerente = User(
        username="gerente_juan",
        full_name="Juan Director",
        email="j.director@empresa.com",
        role=UserRole.GERENTE.value,
        telegram_user_id=2001,
        is_active=True,
    )
    almacenero = User(
        username="almacen_pedro",
        full_name="Pedro Almacenero",
        email="p.almacen@empresa.com",
        role=UserRole.ALMACENERO.value,
        telegram_user_id=3001,
        is_active=True,
    )
    vendedor = User(
        username="vendedor_lucia",
        full_name="Lucia Vendedora",
        email="l.ventas@empresa.com",
        role=UserRole.VENDEDOR.value,
        telegram_user_id=4001,
        is_active=True,
    )
    session.add_all([admin, gerente, almacenero, vendedor])
    session.flush()

    # 3. Productos y Stock
    p1 = Product(
        sku="TAL-4402",
        name="Taladro Percutor Industrial 850W",
        description="Taladro percutor reversible de alta potencia",
        category="Herramientas",
        unit_measure="UND",
        cost_price=45.0,
        sale_price=89.90,
        stock_minimo=15.0,
    )
    p2 = Product(
        sku="AMO-1150",
        name="Amoladora Angular 4-1/2 1100W",
        description="Amoladora para corte y desbaste de metales",
        category="Herramientas",
        unit_measure="UND",
        cost_price=35.0,
        sale_price=69.90,
        stock_minimo=10.0,
    )
    p3 = Product(
        sku="TOR-8820",
        name="Caja Tornillos Autoperforantes 1000u",
        description="Tornillos para tabiqueria punta broca",
        category="Fijaciones",
        unit_measure="CJA",
        cost_price=12.0,
        sale_price=24.50,
        stock_minimo=25.0,
    )
    p4 = Product(
        sku="DIS-2001",
        name="Disco de Corte Metal 4.5 Pulgadas",
        description="Disco abrasivo fino para acero inoxidable",
        category="Accesorios",
        unit_measure="UND",
        cost_price=1.2,
        sale_price=2.90,
        stock_minimo=50.0,
    )
    session.add_all([p1, p2, p3, p4])
    session.flush()

    # Stock (algunos con stock critico para activar alertas)
    s1 = Stock(product_id=p1.id, warehouse_id=w_main.id, quantity=8.0)  # Critico (minimo 15)
    s2 = Stock(product_id=p2.id, warehouse_id=w_main.id, quantity=30.0)
    s3 = Stock(product_id=p3.id, warehouse_id=w_main.id, quantity=5.0)  # Critico (minimo 25)
    s4 = Stock(product_id=p4.id, warehouse_id=w_sec.id, quantity=120.0)
    session.add_all([s1, s2, s3, s4])

    # 4. Ordenes de Compra Pendientes
    po1 = PurchaseOrder(
        order_number="OC-2026-001",
        supplier_name="Ferreterias Industriales S.A.",
        total_amount=1850.0,
        status="PENDIENTE",
        created_by_id=admin.id,
    )
    po2 = PurchaseOrder(
        order_number="OC-2026-002",
        supplier_name="Distribuidora de Herramientas Global",
        total_amount=3420.50,
        status="PENDIENTE",
        created_by_id=admin.id,
    )
    session.add_all([po1, po2])
    session.commit()
    print("[INFO] Base de datos inicializada con existencias y ordenes de compra.")


def run_interactive_cli() -> None:
    """Ejecuta el simulador interactivo de consola para pruebas locales."""
    init_db()
    with get_session() as session:
        seed_demo_data(session)

    # Iniciar demonio de monitoreo en segundo plano
    monitor = AlertMonitorDaemon(interval_seconds=600)
    monitor.start()

    print("\n" + "=" * 60)
    print(" Agente de Telegram ERP - Simulador de Consola Activo")
    print(" Usuarios demo pre-vinculados:")
    print("   * ID 1001: Carlos Administrador (ADMIN)")
    print("   * ID 2001: Juan Director (GERENTE)")
    print("   * ID 3001: Pedro Almacenero (ALMACENERO)")
    print("   * ID 4001: Lucia Vendedora (VENDEDOR)")
    print(" Comandos disponibles:")
    print("   - /stock <SKU o nombre> : Consultar stock")
    print("   - /alertas : Ver articulos en stock critico")
    print("   - /ordenes : Ver ordenes de compra pendientes")
    print("   - /pedido <cliente> <sku> <cant> : Emitir cotizacion")
    print("   - /confirmar_pedido <id> <bodega_id> : Despachar")
    print("   - /reporte : Generar PDF de valorizacion")
    print("   - /reporte_kardex <SKU> : Generar PDF de Kardex")
    print("   - /cambiar_usuario <ID> : Alternar usuario Telegram")
    print("   - Preguntas en lenguaje natural ('cuanto queda de taladro')")
    print("   - 'salir' para terminar")
    print("=" * 60 + "\n")

    current_user_id = 2001  # Inicia por defecto como Juan Director (GERENTE)

    while True:
        try:
            prompt_str = f"[Telegram User ID: {current_user_id}] > "
            user_input = input(prompt_str).strip()
            if not user_input:
                continue

            if user_input.lower() in ("salir", "exit", "quit"):
                print("[INFO] Finalizando simulador y deteniendo monitor...")
                monitor.stop()
                break

            if user_input.startswith("/cambiar_usuario"):
                parts = user_input.split()
                if len(parts) > 1 and parts[1].isdigit():
                    current_user_id = int(parts[1])
                    print(f"[INFO] Usuario activo cambiado a ID: {current_user_id}")
                    continue

            with get_session() as session:
                if user_input.startswith("/start"):
                    response = BotCommandHandler.handle_start(current_user_id, session)
                elif user_input.startswith("/vincular"):
                    parts = user_input.split()
                    otp = parts[1] if len(parts) > 1 else ""
                    response = BotCommandHandler.handle_link(current_user_id, otp, session)
                elif user_input.startswith("/stock"):
                    param = user_input[len("/stock"):].strip()
                    response = BotCommandHandler.handle_stock(current_user_id, param, session)
                elif user_input.startswith("/kardex"):
                    param = user_input[len("/kardex"):].strip()
                    response = BotCommandHandler.handle_kardex(current_user_id, param, session)
                elif user_input.startswith("/alertas"):
                    response = BotCommandHandler.handle_alertas(current_user_id, session)
                elif user_input.startswith("/ordenes"):
                    response = BotCommandHandler.handle_ordenes_pendientes(current_user_id, session)
                elif user_input.startswith("/aprobar"):
                    parts = user_input.split()
                    oid = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                    response = BotCommandHandler.handle_aprobar_orden(current_user_id, oid, session)
                elif user_input.startswith("/rechazar"):
                    parts = user_input.split(maxsplit=2)
                    oid = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                    reason = parts[2] if len(parts) > 2 else "Sin motivo"
                    response = BotCommandHandler.handle_rechazar_orden(current_user_id, oid, reason, session)
                elif user_input.startswith("/pedido"):
                    parts = user_input.split()
                    if len(parts) >= 4:
                        cust = parts[1]
                        sku = parts[2]
                        try:
                            qty = float(parts[3])
                            response = BotCommandHandler.handle_pedido(current_user_id, cust, sku, qty, session)
                        except ValueError:
                            response = "Error: La cantidad debe ser un numero valido."
                    else:
                        response = "Uso: /pedido <NombreCliente> <SKU> <Cantidad>"
                elif user_input.startswith("/confirmar_pedido"):
                    parts = user_input.split()
                    if len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit():
                        oid = int(parts[1])
                        wid = int(parts[2])
                        response = BotCommandHandler.handle_confirmar_pedido(current_user_id, oid, wid, session)
                    else:
                        response = "Uso: /confirmar_pedido <ID_PEDIDO> <ID_BODEGA>"
                elif user_input.startswith("/reporte_kardex"):
                    param = user_input[len("/reporte_kardex"):].strip()
                    msg, filepath = BotCommandHandler.handle_reporte_kardex(current_user_id, param, session)
                    response = f"{msg}\nArchivo en disco: {filepath}" if filepath else msg
                elif user_input.startswith("/reporte"):
                    msg, filepath = BotCommandHandler.handle_reporte(current_user_id, session)
                    response = f"{msg}\nArchivo en disco: {filepath}" if filepath else msg
                else:
                    # Enrutamiento NLP por lenguaje natural
                    response = BotCommandHandler.handle_free_text(current_user_id, user_input, session)

                print("\n" + response + "\n")

        except KeyboardInterrupt:
            print("\n[INFO] Simulador interrumpido.")
            monitor.stop()
            break


def main() -> int:
    """Punto de entrada de ejecucion."""
    parser = argparse.ArgumentParser(description="Agente de Telegram para Gestion ERP e Inventarios")
    parser.add_argument("--interactive", action="store_true", help="Ejecuta en modo simulador interactivo de consola")
    parser.add_argument("--token", type=str, help="Token del Bot de Telegram para modo en vivo")
    args = parser.parse_args()

    token = args.token or os.environ.get("TELEGRAM_BOT_TOKEN")

    if args.interactive or not token:
        print("[INFO] No se especifico TELEGRAM_BOT_TOKEN. Iniciando modo simulador de consola interactivo...")
        run_interactive_cli()
        return 0

    print("[INFO] Conectando bot oficial de Telegram con token provisto...")
    init_db()
    with get_session() as session:
        seed_demo_data(session)

    from src.bot.telegram_bot import TelegramERPBot

    bot = TelegramERPBot(token=token)
    bot.run_polling()
    return 0


if __name__ == "__main__":
    sys.exit(main())
