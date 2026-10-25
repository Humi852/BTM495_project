import json
import logging
import sqlite3
import sys
import threading
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.apis.local_website_api import create_server, ensure_local_demo_login
from backend.apis.profile_api import ManageProfile
from backend.models.customer import Customer


class LocalDryRunWebsiteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test.db"
        with closing(sqlite3.connect(self.database_path)) as connection:
            schema_path = Path(__file__).resolve().parents[1] / "database" / "schema.sql"
            connection.executescript(schema_path.read_text(encoding="utf-8"))
            connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
            connection.executemany(
                "INSERT INTO sample (id) VALUES (?)",
                [(1,), (2,)],
            )
            connection.execute(
                "INSERT INTO customer (customer_id, name) "
                "VALUES (1, 'Test Customer')"
            )
            connection.execute(
                "INSERT INTO orders (order_id, customer_id, totalAmount) "
                "VALUES (101, 1, 42.50)"
            )
            connection.commit()

        self.database_patch = patch(
            "backend.apis.local_website_api.DB_PATH",
            self.database_path,
        )
        self.database_patch.start()
        self.server = create_server("127.0.0.1", 0)
        self.server_thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.server_thread.start()
        host, port = self.server.server_address[:2]
        self.base_url = f"http://{host}:{port}"
        self.api_url = f"{self.base_url}/api/status"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join()
        self.database_patch.stop()
        self.temp_dir.cleanup()

    def test_status_reports_readable_tables_and_row_counts(self) -> None:
        with urlopen(self.api_url) as response:
            self.assertEqual(response.status, 200)
            payload = json.load(response)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["database"], "test.db")
        self.assertEqual(
            payload["tables"],
            [
                {"name": "admin", "rows": 0},
                {"name": "appointment", "rows": 0},
                {"name": "customer", "rows": 1},
                {"name": "event", "rows": 0},
                {"name": "event_registration", "rows": 0},
                {"name": "inventory", "rows": 0},
                {"name": "inventory_history", "rows": 0},
                {"name": "item", "rows": 0},
                {"name": "order_item", "rows": 0},
                {"name": "orders", "rows": 1},
                {"name": "payment", "rows": 0},
                {"name": "sample", "rows": 2},
                {"name": "shopping_cart", "rows": 0},
                {"name": "status", "rows": 12},
            ],
        )

        with closing(sqlite3.connect(self.database_path)) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM sample").fetchone()[0],
                2,
            )

    def test_frontend_page_is_served(self) -> None:
        page_url = self.base_url + "/"
        with urlopen(page_url) as response:
            self.assertEqual(response.status, 200)
            page = response.read().decode("utf-8")
        with urlopen(self.base_url + "/local_website.js") as response:
            script = response.read().decode("utf-8")

        self.assertIn("Local dry-run website", page)
        self.assertIn('id="login-form"', page)
        self.assertIn("login@example.com", page)
        self.assertIn("1234", page)
        self.assertIn('id="payment-dialog"', page)
        self.assertIn('id="payment-history"', page)
        self.assertIn("/api/dashboard", script)
        self.assertIn("/api/login", script)
        self.assertIn("/api/payments", script)

    def test_login_endpoint_calls_profile_login_and_returns_role(self) -> None:
        ManageProfile(self.database_path).createAccount(
            Customer(name="Login Test", email="login@example.com"),
            "test-password",
        )

        with self.assertLogs("backend", level="INFO") as logs:
            with self._post_login(
                {"email": "login@example.com", "password": "test-password"}
            ) as response:
                self.assertEqual(response.status, 200)
                payload = json.load(response)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(
            payload["user"],
            {"name": "Login Test", "is_admin": False},
        )
        log_output = "\n".join(logs.output)
        self.assertIn(
            "Login input received (email supplied, password supplied)",
            log_output,
        )
        self.assertIn("Login output: successful authentication", log_output)
        self.assertNotIn("test-password", log_output)
        self.assertNotIn("login@example.com", log_output)

    def test_local_demo_login_is_created_idempotently(self) -> None:
        ensure_local_demo_login(self.database_path)
        ensure_local_demo_login(self.database_path)

        user = ManageProfile(self.database_path).login(
            "login@example.com",
            "1234",
        )
        self.assertIsNotNone(user)
        assert user is not None
        self.assertEqual(user.name, "Local Dry-Run")
        self.assertFalse(user.isAdmin)

        with closing(sqlite3.connect(self.database_path)) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM customer WHERE email = ?",
                    ("login@example.com",),
                ).fetchone()[0],
                1,
            )

    def test_local_demo_login_does_not_replace_existing_account(self) -> None:
        profile = ManageProfile(self.database_path)
        profile.createAccount(
            Customer(name="Existing Login", email="login@example.com"),
            "existing-password",
        )

        with self.assertRaisesRegex(RuntimeError, "already in use"):
            ensure_local_demo_login(self.database_path)

        self.assertIsNotNone(
            profile.login("login@example.com", "existing-password")
        )

    def test_login_endpoint_rejects_incorrect_credentials(self) -> None:
        with self.assertLogs("backend", level="WARNING") as logs:
            with self._post_login(
                {"email": "missing@example.com", "password": "wrong-password"}
            ) as response:
                self.assertEqual(response.status, 401)
                payload = json.load(response)

        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["message"], "Email or password is incorrect.")
        self.assertIn("Login output: rejected credentials", "\n".join(logs.output))
        self.assertNotIn("wrong-password", "\n".join(logs.output))

    def test_dashboard_shows_orders_and_payment_history(self) -> None:
        with self.assertLogs("backend", level="DEBUG") as logs:
            with urlopen(self.base_url + "/api/dashboard") as response:
                self.assertEqual(response.status, 200)
                payload = json.load(response)

        self.assertEqual(
            payload["orders"],
            [
                {
                    "order_id": 101,
                    "order_date": None,
                    "total_amount": 42.5,
                    "paid": False,
                }
            ],
        )
        self.assertEqual(payload["payments"], [])
        log_output = "\n".join(logs.output)
        self.assertIn("get_dashboard_data: SELECT ", log_output)
        self.assertIn("| found 1 row(s)", log_output)
        self.assertIn(
            "Backend output: Dashboard loaded: 1 order, $42.50 total, "
            "0 payment record(s). Orders: #101 $42.50, date unknown, unpaid.",
            log_output,
        )
        self.assertRegex(
            log_output,
            r"HTTP GET /api/dashboard -> OK in \d+\.\d+ ms",
        )
        self.assertNotIn("127.0.0.1 - - [", log_output)

    def test_dashboard_marks_paid_orders_and_lists_payments(self) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                "INSERT INTO payment "
                "(order_id, paymentDateTime, amount, paymentMethod, statusID) "
                "VALUES (?, ?, ?, ?, (SELECT statusID FROM status "
                "WHERE category = 'payment' AND name = 'Paid'))",
                (101, "2025-01-01 12:00:00", 42.5, "Credit Card"),
            )
            connection.commit()

        with urlopen(self.base_url + "/api/dashboard") as response:
            self.assertEqual(response.status, 200)
            payload = json.load(response)

        self.assertTrue(payload["orders"][0]["paid"])
        self.assertEqual(
            payload["payments"],
            [
                {
                    "payment_id": 1,
                    "order_id": 101,
                    "payment_date": "2025-01-01 12:00:00",
                    "amount": 42.5,
                    "payment_method": "Credit Card",
                    "paid_status": True,
                }
            ],
        )

    def test_dashboard_does_not_mark_pending_or_failed_payments_paid(self) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            for status_name in ("Pending", "Failed"):
                connection.execute(
                    "INSERT INTO payment "
                    "(order_id, paymentDateTime, amount, paymentMethod, statusID) "
                    "VALUES (?, ?, ?, ?, (SELECT statusID FROM status "
                    "WHERE category = 'payment' AND name = ?))",
                    (101, "2025-01-01 12:00:00", 42.5, "Cash", status_name),
                )
            connection.commit()

        with urlopen(self.base_url + "/api/dashboard") as response:
            payload = json.load(response)

        self.assertFalse(payload["orders"][0]["paid"])
        self.assertEqual(
            [payment["paid_status"] for payment in payload["payments"]],
            [False, False],
        )

    def test_sample_order_is_created_and_reused_until_paid(self) -> None:
        request = Request(
            self.base_url + "/api/sample-orders",
            data=b"",
            method="POST",
        )
        with urlopen(request) as response:
            self.assertEqual(response.status, 201)
            first_payload = json.load(response)

        with urlopen(request) as response:
            self.assertEqual(response.status, 201)
            second_payload = json.load(response)

        self.assertEqual(first_payload, second_payload)
        self.assertEqual(first_payload["order"]["total_amount"], 50.0)
        with closing(sqlite3.connect(self.database_path)) as connection:
            sample_user_count = connection.execute(
                "SELECT COUNT(*) FROM customer "
                "WHERE email = 'local-payment-demo@example.invalid'"
            ).fetchone()[0]
            sample_order_count = connection.execute(
                "SELECT COUNT(*) FROM orders WHERE customer_id = "
                "(SELECT customer_id FROM customer "
                "WHERE email = 'local-payment-demo@example.invalid')"
            ).fetchone()[0]
        self.assertEqual(sample_user_count, 1)
        self.assertEqual(sample_order_count, 1)

    def _call(self, method: str, path: str, payload: dict | None = None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            return urlopen(request)
        except HTTPError as error:
            return error

    def _add_payment(self, order_id: int = 101) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                "INSERT INTO payment "
                "(order_id, paymentDateTime, amount, paymentMethod, statusID) "
                "VALUES (?, '2025-01-01 12:00:00', 42.5, 'Credit Card', "
                "(SELECT statusID FROM status "
                "WHERE category = 'payment' AND name = 'Paid'))",
                (order_id,),
            )
            connection.commit()

    def _count(self, table: str) -> int:
        with closing(sqlite3.connect(self.database_path)) as connection:
            return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def _json(self, method: str, path: str, payload: dict | None = None):
        with self._call(method, path, payload) as response:
            return response.status, json.load(response)

    def test_inventory_routes_cover_every_inventory_api(self) -> None:
        status, body = self._json(
            "POST",
            "/api/inventory",
            {"item_id": 5, "name": "Tube", "price": 8.5, "stock_quantity": 4},
        )
        self.assertEqual(status, 201)
        status, body = self._json(
            "PATCH",
            "/api/inventory/5",
            {"price": 9, "stock_quantity": 2, "reason": "Cycle count"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["stockQuantity"], [4, 2])
        self.assertEqual(self._json("PATCH", "/api/inventory/5", {"price": 9})[0], 400)

        _, body = self._json("GET", "/api/inventory")
        self.assertEqual(
            [(i["item_id"], i["price"], i["stock_quantity"]) for i in body["items"]],
            [(5, 9, 2)],
        )
        _, body = self._json("GET", "/api/inventory/5/history")
        self.assertEqual(
            [(h["oldQuantity"], h["newQuantity"]) for h in body["history"]],
            [(None, 4), (4, 2)],
        )

        self.assertEqual(self._json("GET", "/api/inventory/9/history")[0], 404)
        self.assertEqual(self._json("POST", "/api/inventory", {"bogus": 1})[0], 400)
        self.assertEqual(self._json("PATCH", "/api/inventory/5", {"bogus": 1})[0], 400)
        self.assertEqual(self._json("DELETE", "/api/inventory/5")[0], 200)
        self.assertEqual(self._json("DELETE", "/api/inventory/5")[0], 404)
        self.assertEqual(self._count("inventory"), 0)
        self.assertEqual(self._count("inventory_history"), 0)

    def test_event_registration_routes(self) -> None:
        status, body = self._json(
            "POST", "/api/events", {"name": "Ride", "participant_limit": 1}
        )
        self.assertEqual(status, 201)
        event_id = body["event_id"]
        self.assertEqual(self._json("POST", "/api/events", {"name": " "})[0], 400)

        register = {"event_id": event_id, "customer_id": 1}
        self.assertEqual(self._json("POST", "/api/event-registrations", register)[0], 201)
        self.assertEqual(self._json("POST", "/api/event-registrations", register)[0], 400)
        self.assertEqual(
            self._json("POST", "/api/event-registrations", {"event_id": "x"})[0], 400
        )
        _, body = self._json("GET", "/api/events")
        self.assertEqual(body["events"][0]["customer_ids"], [1])
        self.assertEqual(body["customers"][0]["customer_id"], 1)

        path = f"/api/event-registrations/{event_id}/1"
        self.assertEqual(self._json("DELETE", path)[0], 200)
        self.assertEqual(self._json("DELETE", path)[0], 404)
        self.assertEqual(self._json("DELETE", "/api/event-registrations/x/1")[0], 404)
        self.assertEqual(self._json("DELETE", f"/api/events/{event_id}")[0], 200)
        self.assertEqual(self._json("DELETE", f"/api/events/{event_id}")[0], 404)

    def test_edit_order_and_payment_amounts(self) -> None:
        self._add_payment()
        with self._call("PATCH", "/api/orders/101", {"amount": 10.5}) as response:
            self.assertEqual(response.status, 200)
        with self._call("PATCH", "/api/payments/1", {"amount": 7}) as response:
            self.assertEqual(response.status, 200)
        with urlopen(self.base_url + "/api/dashboard") as response:
            payload = json.load(response)
        self.assertEqual(payload["orders"][0]["total_amount"], 10.5)
        self.assertEqual(payload["payments"][0]["amount"], 7)

    def test_edit_rejects_bad_amount_and_missing_records(self) -> None:
        for body in ({"amount": 0}, {"amount": "5"}, {"amount": True}, {}):
            with self._call("PATCH", "/api/orders/101", body) as response:
                self.assertEqual(response.code, 400)
        with self._call("PATCH", "/api/orders/999", {"amount": 5}) as response:
            self.assertEqual(response.code, 404)
        with self._call("PATCH", "/api/orders", {"amount": 5}) as response:
            self.assertEqual(response.code, 404)
        with self._call("PATCH", "/api/orders/101", None) as response:
            self.assertEqual(response.code, 400)

    def test_delete_single_order_removes_its_payments(self) -> None:
        self._add_payment()
        with self._call("DELETE", "/api/orders/101") as response:
            self.assertEqual(response.status, 200)
        self.assertEqual(self._count("orders"), 0)
        self.assertEqual(self._count("payment"), 0)
        with self._call("DELETE", "/api/orders/101") as response:
            self.assertEqual(response.code, 404)

    def test_delete_single_payment_keeps_order(self) -> None:
        self._add_payment()
        with self._call("DELETE", "/api/payments/1") as response:
            self.assertEqual(response.status, 200)
        self.assertEqual(self._count("payment"), 0)
        self.assertEqual(self._count("orders"), 1)

    def test_remove_all_payments_and_orders(self) -> None:
        self._add_payment()
        with self._call("DELETE", "/api/payments") as response:
            self.assertEqual(response.status, 200)
        self.assertEqual((self._count("payment"), self._count("orders")), (0, 1))
        self._add_payment()
        with self._call("DELETE", "/api/orders") as response:
            self.assertEqual(response.status, 200)
        self.assertEqual((self._count("payment"), self._count("orders")), (0, 0))

    def test_unknown_record_routes_are_not_found(self) -> None:
        for method, path in (
            ("DELETE", "/api/items/1"),
            ("DELETE", "/api/orders/abc"),
            ("DELETE", "/api/orders/1/2"),
        ):
            with self._call(method, path) as response:
                self.assertEqual(response.code, 404)

    def test_card_form_defaults_are_valid_and_prefilled(self) -> None:
        with urlopen(self.base_url + "/") as response:
            page = response.read().decode("utf-8")
        for value in ("4242424242424242", "12/30", "123"):
            self.assertIn(f'value="{value}"', page)

    def _post_payment(self, payload: dict[str, object]):
        request = Request(
            self.base_url + "/api/payments",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            return urlopen(request)
        except HTTPError as error:
            return error

    def _post_login(self, payload: dict[str, object]):
        request = Request(
            self.base_url + "/api/login",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            return urlopen(request)
        except HTTPError as error:
            return error

    def test_approved_payment_is_processed_without_database_write(self) -> None:
        with self._post_payment(
            {
                "order_id": 101,
                "card_number": "4242424242424242",
                "expiration_date": "12/30",
                "cvv": "123",
            }
        ) as response:
            self.assertEqual(response.status, 200)
            payload = json.load(response)

        self.assertTrue(payload["payment"]["paid_status"])
        self.assertEqual(payload["payment"]["amount"], 42.5)
        with closing(sqlite3.connect(self.database_path)) as connection:
            count = connection.execute("SELECT COUNT(*) FROM payment").fetchone()[0]
        self.assertEqual(count, 0)

    def test_declined_test_card_is_processed_without_database_write(self) -> None:
        with self._post_payment(
            {
                "order_id": 101,
                "card_number": "4000000000000002",
                "expiration_date": "12/30",
                "cvv": "123",
            }
        ) as response:
            self.assertEqual(response.status, 200)
            payload = json.load(response)

        self.assertFalse(payload["payment"]["paid_status"])
        self.assertEqual(payload["payment"]["details"], "Payment Failed")
        self.assertIsNone(payload["payment"]["payment_date"])
        with closing(sqlite3.connect(self.database_path)) as connection:
            count = connection.execute("SELECT COUNT(*) FROM payment").fetchone()[0]
        self.assertEqual(count, 0)

    def test_unapproved_card_returns_failed_without_database_write(self) -> None:
        with self._post_payment(
            {
                "order_id": 101,
                "card_number": "not-a-card",
                "expiration_date": "12/30",
                "cvv": "123",
            }
        ) as response:
            self.assertEqual(response.status, 200)
            payload = json.load(response)

        self.assertFalse(payload["payment"]["paid_status"])
        self.assertEqual(payload["payment"]["details"], "Payment Failed")
        with closing(sqlite3.connect(self.database_path)) as connection:
            count = connection.execute("SELECT COUNT(*) FROM payment").fetchone()[0]
        self.assertEqual(count, 0)

    def test_same_order_can_be_processed_again_without_payment_history(self) -> None:
        payment = {
            "order_id": 101,
            "card_number": "4242424242424242",
            "expiration_date": "12/30",
            "cvv": "123",
        }
        with self._post_payment(payment) as response:
            self.assertEqual(response.status, 200)
        with self._post_payment(payment) as response:
            self.assertEqual(response.status, 200)

        with closing(sqlite3.connect(self.database_path)) as connection:
            count = connection.execute("SELECT COUNT(*) FROM payment").fetchone()[0]
        self.assertEqual(count, 0)

    def test_unrecognized_card_value_returns_failed(self) -> None:
        with self._post_payment(
            {
                "order_id": 101,
                "card_number": 4242424242424242,
                "expiration_date": "12/30",
                "cvv": "123",
            }
        ) as response:
            self.assertEqual(response.status, 200)
            payload = json.load(response)

        self.assertFalse(payload["payment"]["paid_status"])

    def test_wrong_order_id_type_returns_false(self) -> None:
        with self._post_payment(
            {
                "order_id": [],
                "card_number": "4242424242424242",
                "expiration_date": "12/30",
                "cvv": "123",
            }
        ) as response:
            self.assertEqual(response.status, 400)
            payload = json.load(response)

        self.assertFalse(payload["paid"])

    def test_status_reports_missing_database_as_an_error(self) -> None:
        self.database_path.unlink()

        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)
        with self.assertRaises(HTTPError) as error:
            urlopen(self.api_url)

        self.assertEqual(error.exception.code, 500)
        payload = json.load(error.exception)
        self.assertEqual(payload["status"], "error")
        self.assertTrue(payload["message"])


if __name__ == "__main__":
    unittest.main()
