import json
import sqlite3
from contextlib import closing
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from backend.services.payment import Payment
from database.db import DB_PATH

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


def get_database_status() -> dict[str, object]:
    database_uri = f"{DB_PATH.resolve().as_uri()}?mode=ro"
    with closing(sqlite3.connect(database_uri, uri=True)) as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        ).fetchall()
        table_status = []
        for (table_name,) in tables:
            quoted_name = table_name.replace('"', '""')
            row_count = connection.execute(
                f'SELECT COUNT(*) FROM "{quoted_name}"'
            ).fetchone()[0]
            table_status.append({"name": table_name, "rows": row_count})

    return {
        "status": "ok",
        "database": DB_PATH.name,
        "tables": table_status,
    }


def get_dashboard_data() -> dict[str, object]:
    database_uri = f"{DB_PATH.resolve().as_uri()}?mode=ro"
    with closing(sqlite3.connect(database_uri, uri=True)) as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        ).fetchall()
        table_status = []
        for (table_name,) in tables:
            quoted_name = table_name.replace('"', '""')
            row_count = connection.execute(
                f'SELECT COUNT(*) FROM "{quoted_name}"'
            ).fetchone()[0]
            table_status.append({"name": table_name, "rows": row_count})

        orders = [
            {
                "order_id": order_id,
                "order_date": order_date,
                "total_amount": total_amount,
                "paid": bool(paid),
            }
            for order_id, order_date, total_amount, paid in connection.execute(
                "SELECT o.order_id, o.orderDateTime, o.totalAmount, "
                "EXISTS (SELECT 1 FROM payment p "
                "WHERE p.order_id = o.order_id AND p.paidstatus = 1) "
                "FROM orders o ORDER BY o.order_id DESC"
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
            ) in connection.execute(
                "SELECT payment_id, order_id, paymentDateTime, amount, "
                "paymentMethod, paidstatus, details "
                "FROM payment ORDER BY payment_id DESC"
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
            content_length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._send_json(
                {"status": "error", "message": "Invalid Content-Length header."},
                400,
            )
            return
        if content_length <= 0 or content_length > self.MAX_REQUEST_BYTES:
            self._send_json(
                {"status": "error", "message": "Invalid payment request size."},
                400,
            )
            return

        try:
            payload = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(
                {"status": "error", "message": "Request body must be valid JSON."},
                400,
            )
            return
        if not isinstance(payload, dict):
            self._send_json(
                {"status": "error", "message": "Payment request must be an object."},
                400,
            )
            return

        try:
            order_id = payload.get("order_id")
            with closing(sqlite3.connect(DB_PATH)) as connection:
                order = connection.execute(
                    "SELECT totalAmount FROM orders WHERE order_id = ?",
                    (order_id,),
                ).fetchone()
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
            "Credit Card",
        )
        card_number = payload.get("card_number")
        expiration_date = payload.get("expiration_date")
        cvv = payload.get("cvv")
        payment.processPayment(
            card_number if type(card_number) is str else "",
            expiration_date if type(expiration_date) is str else "",
            cvv if type(cvv) is str else "",
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
                    "paid_status": payment.paidStatus == "Paid",
                    "details": payment.details,
                },
            },
            200,
        )

    def _create_sample_order(self) -> None:
        try:
            with closing(sqlite3.connect(DB_PATH)) as connection:
                customer = connection.execute(
                    "SELECT customer_id FROM customer WHERE email = ?",
                    (self.DEMO_CUSTOMER_EMAIL,),
                ).fetchone()
                if customer is None:
                    cursor = connection.execute(
                        "INSERT INTO customer (name, email) VALUES (?, ?)",
                        ("Local Payment Demo", self.DEMO_CUSTOMER_EMAIL),
                    )
                    customer_id = cursor.lastrowid
                else:
                    customer_id = customer[0]

                order = connection.execute(
                    "SELECT o.order_id, o.orderDateTime, o.totalAmount "
                    "FROM orders o WHERE o.customer_id = ? "
                    "AND NOT EXISTS ("
                    "SELECT 1 FROM payment p "
                    "WHERE p.order_id = o.order_id AND p.paidstatus = 1"
                    ") ORDER BY o.order_id DESC LIMIT 1",
                    (customer_id,),
                ).fetchone()

                if order is None:
                    order_date = datetime.now().isoformat(timespec="seconds")
                    cursor = connection.execute(
                        "INSERT INTO orders (customer_id, orderDateTime, totalAmount) "
                        "VALUES (?, ?, ?)",
                        (customer_id, order_date, self.DEMO_ORDER_AMOUNT),
                    )
                    order = (
                        cursor.lastrowid,
                        order_date,
                        self.DEMO_ORDER_AMOUNT,
                    )
                connection.commit()
        except sqlite3.Error:
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
        except (OSError, sqlite3.Error):
            response = {
                "status": "error",
                "message": "Could not read dashboard data from SQLite.",
            }
            status_code = 500

        self._send_json(response, status_code)

    def _send_json(self, response: dict[str, object], status_code: int) -> None:
        encoded_response = json.dumps(response).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded_response)))
        self.end_headers()
        self.wfile.write(encoded_response)


def create_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), LocalTestRequestHandler)
