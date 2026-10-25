import json
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
        with self.assertLogs("backend", level="INFO") as logs:
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
        self.assertIn("SQL query:\nSELECT", log_output)
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
                "VALUES (?, ?, ?, ?, ?)",
                (101, "2025-01-01 12:00:00", 42.5, "Credit Card", 1),
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

        with self.assertRaises(HTTPError) as error:
            urlopen(self.api_url)

        self.assertEqual(error.exception.code, 500)
        payload = json.load(error.exception)
        self.assertEqual(payload["status"], "error")
        self.assertTrue(payload["message"])


if __name__ == "__main__":
    unittest.main()
