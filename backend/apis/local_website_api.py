import logging
import sqlite3
import time
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from backend.apis.profile_api import ManageProfile
from backend.models.payment import Payment, PaymentMethod, PaymentStatus
from backend.utils.constants import DatabaseColumns, DatabaseTables, DatabaseValues
from backend.utils.http import HTTPRequestError, read_json_object, send_json
from backend.utils.logger import (
    configure_backend_logging,
    get_logger,
    http_status_label,
)
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
LOCAL_DEMO_LOGIN_EMAIL = "login@example.com"
LOCAL_DEMO_LOGIN_PASSWORD = "1234"
logger = get_logger(__name__)


def _database() -> SQLiteQuery:
    return SQLiteQuery(DB_PATH)


def ensure_local_demo_login(database_path: str | Path = DB_PATH) -> None:
    profile = ManageProfile(database_path)
    if profile.login(LOCAL_DEMO_LOGIN_EMAIL, LOCAL_DEMO_LOGIN_PASSWORD) is not None:
        return

    with SQLiteQuery(database_path).transaction(immediate=True) as session:
        for table in (DatabaseTables.ADMIN, DatabaseTables.CUSTOMER):
            existing = session.select_one(
                table,
                (DatabaseColumns.EMAIL,),
                where=(SQLCondition(DatabaseColumns.EMAIL, LOCAL_DEMO_LOGIN_EMAIL),),
            )
            if existing is not None:
                raise RuntimeError(
                    f"Cannot create the local demo login because "
                    f"{LOCAL_DEMO_LOGIN_EMAIL} is already in use."
                )

        # Keep the short smoke-test password hashed without weakening account policy.
        session.insert(
            DatabaseTables.CUSTOMER,
            {
                DatabaseColumns.NAME: "Local Dry-Run",
                DatabaseColumns.EMAIL: LOCAL_DEMO_LOGIN_EMAIL,
                DatabaseColumns.PASSWORD_HASH: profile._hashPassword(
                    LOCAL_DEMO_LOGIN_PASSWORD
                ),
            },
        )


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
        self._request_started = time.perf_counter()
        self._request_logged = False
        self._response_status = 500
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def send_response(self, code: int, message: str | None = None) -> None:
        self._response_status = code
        super().send_response(code, message)

    def finish(self) -> None:
        try:
            super().finish()
        finally:
            if not self._request_logged:
                self._request_logged = True
                request_method = getattr(self, "command", "UNKNOWN")
                request_path = urlsplit(getattr(self, "path", "/")).path
                duration_ms = (time.perf_counter() - self._request_started) * 1000
                if self._response_status >= 500:
                    log_level = logging.ERROR
                elif self._response_status >= 400:
                    log_level = logging.WARNING
                else:
                    log_level = logging.INFO
                logger.log(
                    log_level,
                    "HTTP %s %s -> %s in %.2f ms",
                    request_method,
                    request_path,
                    http_status_label(self._response_status),
                    duration_ms,
                )

    def log_message(self, format: str, *args: object) -> None:
        return

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
        if request_path == "/api/login":
            self._login()
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
            logger.warning("Payment input rejected: %s", error)
            self._send_json({"status": "error", "message": str(error)}, error.status_code)
            return

        order_id = payload.get("order_id")
        if not (
            type(order_id) is int
            or (isinstance(order_id, str) and order_id.isdecimal())
        ):
            logger.warning("Payment input rejected: invalid order ID type")
            self._send_json(
                {"status": "error", "paid": False, "message": "Invalid order ID."},
                400,
            )
            return

        try:
            order = _database().select_one(
                DatabaseTables.ORDERS,
                (DatabaseColumns.TOTAL_AMOUNT,),
                where=(SQLCondition(DatabaseColumns.ORDER_ID, order_id),),
            )
        except sqlite3.Error:
            logger.exception("Could not look up order for payment")
            self._send_json(
                {"status": "error", "message": "Could not process payment request."},
                500,
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

    def _login(self) -> None:
        try:
            payload = read_json_object(
                self,
                self.MAX_REQUEST_BYTES,
                request_name="Login",
            )
        except HTTPRequestError as error:
            logger.warning("Login input rejected: %s", error)
            self._send_json(
                {"status": "error", "message": str(error)},
                error.status_code,
            )
            return

        email = string_value(payload, "email")
        password = string_value(payload, "password")

        try:
            user = ManageProfile(DB_PATH).login(email, password)
        except sqlite3.Error as error:
            logger.exception("Could not process profile login: %s", error)
            self._send_json(
                {"status": "error", "message": "Could not process login."},
                500,
            )
            return

        if user is None:
            logger.warning("Login output: rejected credentials")
            self._send_json(
                {"status": "error", "message": "Email or password is incorrect."},
                401,
            )
            return

        self._send_json(
            {
                "status": "ok",
                "user": {
                    "name": user.name,
                    "is_admin": user.isAdmin,
                },
            },
            200,
        )
        logger.info(
            "Login output: successful authentication (role=%s)",
            "admin" if user.isAdmin else "customer",
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
            logger.exception("Could not create a sample order: %s", error)
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
