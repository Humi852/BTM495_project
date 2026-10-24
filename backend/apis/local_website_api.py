import sqlite3
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from backend.models.payment import Payment, PaymentMethod, PaymentStatus
from backend.utils.constants import DatabaseColumns, DatabaseTables, DatabaseValues
from backend.utils.http import HTTPRequestError, read_json_object, send_json
from backend.utils.logger import configure_backend_logging, get_logger
from backend.utils.sqlite import (
    SQLiteQuery,
    SQLiteSession,
    SQLCondition,
    SQLOrder,
    SQLSortDirection,
)
from backend.utils.validators import string_value
from database.sqlite_database import DB_PATH

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
logger = get_logger(__name__)


def _database() -> SQLiteQuery:
    return SQLiteQuery(DB_PATH)


def _get_table_status(database: SQLiteSession) -> list[dict[str, object]]:
    tables = database.list_tables()
    table_status = []
    for table_name in tables:
        table_status.append(
            {"name": table_name, "rows": database.count(table_name)}
        )
    return table_status


def get_database_status() -> dict[str, object]:
    database = _database()
    with database.session(read_only=True) as session:
        tables = _get_table_status(session)

    return {
        "status": "ok",
        "database": DB_PATH.name,
        "tables": tables,
    }


def get_dashboard_data() -> dict[str, object]:
    database = _database()
    with database.session(read_only=True) as session:
        table_status = _get_table_status(session)
        paid_order_ids = {
            order_id
            for (order_id,) in session.select(
                DatabaseTables.PAYMENT,
                (DatabaseColumns.ORDER_ID,),
                where=(
                    SQLCondition(
                        DatabaseColumns.PAID_STATUS,
                        DatabaseValues.PAID_STATUS_PAID,
                    ),
                ),
            )
        }
        orders = [
            {
                "order_id": order_id,
                "order_date": order_date,
                "total_amount": total_amount,
                "paid": order_id in paid_order_ids,
            }
            for order_id, order_date, total_amount in session.select(
                DatabaseTables.ORDERS,
                (
                    DatabaseColumns.ORDER_ID,
                    DatabaseColumns.ORDER_DATE_TIME,
                    DatabaseColumns.TOTAL_AMOUNT,
                ),
                order_by=(
                    SQLOrder(
                        DatabaseColumns.ORDER_ID,
                        SQLSortDirection.DESCENDING,
                    ),
                ),
            )
        ]
        payments = [
            {
                "payment_id": payment_id,
                "order_id": order_id,
                "payment_date": payment_date,
                "amount": amount,
                "payment_method": payment_method,
                "paid_status": bool(paid_status),
                "details": details,
            }
            for (
                payment_id,
                order_id,
                payment_date,
                amount,
                payment_method,
                paid_status,
                details,
            ) in session.select(
                DatabaseTables.PAYMENT,
                (
                    DatabaseColumns.PAYMENT_ID,
                    DatabaseColumns.ORDER_ID,
                    DatabaseColumns.PAYMENT_DATE_TIME,
                    DatabaseColumns.AMOUNT,
                    DatabaseColumns.PAYMENT_METHOD,
                    DatabaseColumns.PAID_STATUS,
                    DatabaseColumns.DETAILS,
                ),
                order_by=(
                    SQLOrder(
                        DatabaseColumns.PAYMENT_ID,
                        SQLSortDirection.DESCENDING,
                    ),
                ),
            )
        ]

    return {
        "status": "ok",
        "database": DB_PATH.name,
        "tables": table_status,
        "orders": orders,
        "payments": payments,
    }


class LocalTestRequestHandler(SimpleHTTPRequestHandler):
    MAX_REQUEST_BYTES = 8192
    DEMO_CUSTOMER_EMAIL = "local-payment-demo@example.invalid"
    DEMO_ORDER_AMOUNT = 50.00

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def do_GET(self) -> None:
        request_path = urlsplit(self.path).path
        if request_path == "/api/status":
            self._send_database_status()
            return
        if request_path == "/api/dashboard":
            self._send_dashboard_data()
            return
        super().do_GET()

    def do_POST(self) -> None:
        request_path = urlsplit(self.path).path
        if request_path == "/api/sample-orders":
            self._create_sample_order()
            return
        if request_path != "/api/payments":
            self._send_json({"status": "error", "message": "Not found."}, 404)
            return

        try:
            payload = read_json_object(
                self,
                self.MAX_REQUEST_BYTES,
                request_name="Payment",
            )
        except HTTPRequestError as error:
            self._send_json({"status": "error", "message": str(error)}, error.status_code)
            return

        try:
            order_id = payload.get("order_id")
            order = _database().select_one(
                DatabaseTables.ORDERS,
                (DatabaseColumns.TOTAL_AMOUNT,),
                where=(SQLCondition(DatabaseColumns.ORDER_ID, order_id),),
            )
        except (sqlite3.Error, TypeError, ValueError):
            self._send_json(
                {"status": "error", "paid": False, "message": "Invalid order ID."},
                400,
            )
            return

        if order is None:
            self._send_json(
                {"status": "error", "message": "Order was not found."},
                404,
            )
            return

        payment = Payment(
            None,
            order_id,
            order[0],
            PaymentMethod.CREDIT_CARD.value,
        )
        payment.processPayment(
            string_value(payload, "card_number"),
            string_value(payload, "expiration_date"),
            string_value(payload, "cvv"),
        )

        self._send_json(
            {
                "status": "ok",
                "payment": {
                    "order_id": order_id,
                    "payment_date": (
                        payment.paymentDate.isoformat(timespec="seconds")
                        if payment.paymentDate
                        else None
                    ),
                    "amount": payment.amount,
                    "payment_method": payment.paymentMethod,
                    "paid_status": payment.paidStatus == PaymentStatus.PAID,
                    "details": payment.details,
                },
            },
            200,
        )

    def _create_sample_order(self) -> None:
        try:
            with _database().transaction() as connection:
                customer = connection.select_one(
                    DatabaseTables.CUSTOMER,
                    (DatabaseColumns.CUSTOMER_ID,),
                    where=(
                        SQLCondition(
                            DatabaseColumns.EMAIL,
                            self.DEMO_CUSTOMER_EMAIL,
                        ),
                    ),
                )
                if customer is None:
                    result = connection.insert(
                        DatabaseTables.CUSTOMER,
                        {
                            DatabaseColumns.NAME: "Local Payment Demo",
                            DatabaseColumns.EMAIL: self.DEMO_CUSTOMER_EMAIL,
                        },
                    )
                    customer_id = result.lastrowid
                else:
                    customer_id = customer[0]

                customer_orders = connection.select(
                    DatabaseTables.ORDERS,
                    (
                        DatabaseColumns.ORDER_ID,
                        DatabaseColumns.ORDER_DATE_TIME,
                        DatabaseColumns.TOTAL_AMOUNT,
                    ),
                    where=(
                        SQLCondition(DatabaseColumns.CUSTOMER_ID, customer_id),
                    ),
                    order_by=(
                        SQLOrder(
                            DatabaseColumns.ORDER_ID,
                            SQLSortDirection.DESCENDING,
                        ),
                    ),
                )
                paid_order_ids = {
                    order_id
                    for (order_id,) in connection.select(
                        DatabaseTables.PAYMENT,
                        (DatabaseColumns.ORDER_ID,),
                        where=(
                            SQLCondition(
                                DatabaseColumns.PAID_STATUS,
                                DatabaseValues.PAID_STATUS_PAID,
                            ),
                        ),
                    )
                }
                order = next(
                    (
                        candidate
                        for candidate in customer_orders
                        if candidate[0] not in paid_order_ids
                    ),
                    None,
                )

                if order is None:
                    order_date = datetime.now().isoformat(timespec="seconds")
                    result = connection.insert(
                        DatabaseTables.ORDERS,
                        {
                            DatabaseColumns.CUSTOMER_ID: customer_id,
                            DatabaseColumns.ORDER_DATE_TIME: order_date,
                            DatabaseColumns.TOTAL_AMOUNT: self.DEMO_ORDER_AMOUNT,
                        },
                    )
                    order = (
                        result.lastrowid,
                        order_date,
                        self.DEMO_ORDER_AMOUNT,
                    )
        except sqlite3.Error as error:
            logger.error("Could not create a sample order: %s", error)
            self._send_json(
                {"status": "error", "message": "Could not create a sample order."},
                500,
            )
            return

        self._send_json(
            {
                "status": "ok",
                "order": {
                    "order_id": order[0],
                    "order_date": order[1],
                    "total_amount": order[2],
                    "paid": False,
                },
            },
            201,
        )

    def _send_database_status(self) -> None:
        try:
            response = get_database_status()
            status_code = 200
        except (OSError, sqlite3.Error) as error:
            logger.error("Could not read database status: %s", error)
            response = {
                "status": "error",
                "message": str(error),
            }
            status_code = 500

        self._send_json(response, status_code)

    def _send_dashboard_data(self) -> None:
        try:
            response = get_dashboard_data()
            status_code = 200
        except (OSError, sqlite3.Error) as error:
            logger.error("Could not read dashboard data from SQLite: %s", error)
            response = {
                "status": "error",
                "message": "Could not read dashboard data from SQLite.",
            }
            status_code = 500

        self._send_json(response, status_code)

    def _send_json(self, response: dict[str, object], status_code: int) -> None:
        send_json(self, response, status_code)


def create_server(host: str, port: int) -> ThreadingHTTPServer:
    configure_backend_logging()
    return ThreadingHTTPServer((host, port), LocalTestRequestHandler)
