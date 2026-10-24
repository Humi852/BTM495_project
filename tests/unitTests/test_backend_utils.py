import io
import json
import logging
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.utils.http import HTTPRequestError, read_json_object, send_json
from backend.utils.logger import BackendFormatter, http_status_label
from backend.utils.sqlite import (
    SQLColumnDefinition,
    SQLComparison,
    SQLCondition,
    SQLDataType,
    SQLOrder,
    SQLSortDirection,
    SQLiteQuery,
    SQLBuilder,
    quote_identifier,
)
from backend.utils.validators import (
    is_valid_card_number,
    is_valid_cvv,
    is_valid_email,
    is_valid_expiration_date,
    is_valid_password,
    is_valid_profile,
    string_value,
)


class FakeRequestHandler:
    def __init__(self, payload: bytes, content_length: str | None = None) -> None:
        self.headers = {
            "Content-Length": content_length or str(len(payload)),
        }
        self.rfile = io.BytesIO(payload)
        self.wfile = io.BytesIO()
        self.response_status: int | None = None
        self.response_headers: dict[str, str] = {}

    def send_response(self, status_code: int) -> None:
        self.response_status = status_code

    def send_header(self, name: str, value: str) -> None:
        self.response_headers[name] = value

    def end_headers(self) -> None:
        pass


class SQLiteQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.database = SQLiteQuery(Path(self.temp_dir.name) / "test.db")
        self.database.create_table(
            "record",
            (SQLColumnDefinition("value", SQLDataType.TEXT, not_null=True),),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_query_methods_use_parameters_and_return_execution_details(self) -> None:
        result = self.database.execute(
            "INSERT INTO record (value) VALUES (?)",
            ("value",),
        )

        self.assertEqual(result.lastrowid, 1)
        self.assertEqual(result.rowcount, 1)
        self.assertEqual(
            self.database.fetch_one("SELECT value FROM record WHERE value = ?", ("value",)),
            ("value",),
        )

    def test_transaction_rolls_back_when_operation_raises(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "abort"):
            with self.database.transaction(immediate=True) as session:
                session.execute("INSERT INTO record (value) VALUES (?)", ("rolled back",))
                raise RuntimeError("abort")

        self.assertEqual(
            self.database.fetch_one("SELECT COUNT(*) FROM record"),
            (0,),
        )

    def test_read_only_query_reads_database(self) -> None:
        self.database.execute("INSERT INTO record (value) VALUES (?)", ("read",))

        self.assertEqual(
            self.database.fetch_all("SELECT value FROM record", read_only=True),
            [("read",)],
        )

    def test_quote_identifier_escapes_embedded_quotes(self) -> None:
        self.assertEqual(quote_identifier('odd"name'), '"odd""name"')

    def test_generic_crud_methods_use_bound_values(self) -> None:
        inserted = self.database.insert("record", {"value": "O'Reilly"})
        self.assertEqual(inserted.rowcount, 1)

        self.assertEqual(
            self.database.select_one(
                "record",
                ("value",),
                where=(SQLCondition("value", "O'Reilly"),),
            ),
            ("O'Reilly",),
        )

        updated = self.database.update(
            "record",
            {"value": "updated"},
            where=(SQLCondition("value", "O'Reilly"),),
        )
        self.assertEqual(updated.rowcount, 1)

        deleted = self.database.delete(
            "record",
            where=(SQLCondition("value", "updated"),),
        )
        self.assertEqual(deleted.rowcount, 1)
        self.assertEqual(self.database.count("record"), 0)

    def test_sql_logs_are_pretty_and_redact_bound_values(self) -> None:
        with self.assertLogs("backend.utils.sqlite", level="INFO") as logs:
            self.database.insert(
                "record",
                {"value": "private-value"},
            )

        output = "\n".join(logs.output)
        self.assertIn('INSERT INTO "record" ("value")\n  VALUES (?)', output)
        self.assertIn("parameters: 1 value(s) redacted", output)
        self.assertNotIn("private-value", output)

    def test_query_builder_handles_in_null_order_and_parameter_order(self) -> None:
        statement, parameters = SQLBuilder.select(
            "record",
            ("value",),
            where=(
                SQLCondition("value", ("one", "two"), SQLComparison.IN),
                SQLCondition("value", None),
            ),
            order_by=(SQLOrder("value", SQLSortDirection.DESCENDING),),
            limit=4,
        )

        self.assertEqual(
            statement,
            'SELECT "value" FROM "record" WHERE "value" IN (?, ?) '
            'AND "value" IS NULL ORDER BY "value" DESC LIMIT ?',
        )
        self.assertEqual(parameters, ("one", "two", 4))

    def test_mutations_require_conditions_and_empty_in_matches_nothing(self) -> None:
        with self.assertRaisesRegex(ValueError, "condition"):
            SQLBuilder.update("record", {"value": "unsafe"}, where=())
        with self.assertRaisesRegex(ValueError, "condition"):
            SQLBuilder.delete("record", where=())

        self.database.insert("record", {"value": "present"})
        self.assertEqual(
            self.database.select(
                "record",
                ("value",),
                where=(SQLCondition("value", (), SQLComparison.IN),),
            ),
            [],
        )
        self.assertEqual(self.database.list_tables(), ["record"])


class ValidationHelperTests(unittest.TestCase):
    def test_profile_email_and_password_validation(self) -> None:
        self.assertTrue(is_valid_email("student@example.edu"))
        self.assertFalse(is_valid_email("student@@example.edu"))
        self.assertTrue(is_valid_password("password"))
        self.assertFalse(is_valid_password("short"))
        self.assertTrue(is_valid_profile("Student", "student@example.edu"))
        self.assertFalse(is_valid_profile(" ", "student@example.edu"))

    def test_payment_field_validation(self) -> None:
        self.assertTrue(is_valid_card_number("4242424242424242"))
        self.assertFalse(is_valid_card_number("4242"))
        self.assertTrue(is_valid_expiration_date("12/30"))
        self.assertFalse(is_valid_expiration_date("13/30"))
        self.assertTrue(is_valid_cvv("123"))
        self.assertFalse(is_valid_cvv("12"))
        self.assertEqual(string_value({"card_number": "123"}, "card_number"), "123")
        self.assertEqual(string_value({"card_number": 123}, "card_number"), "")


class HTTPHelperTests(unittest.TestCase):
    def test_warning_and_error_logs_use_terminal_colors(self) -> None:
        class TerminalStream(io.StringIO):
            def isatty(self) -> bool:
                return True

        formatter = BackendFormatter(TerminalStream())
        warning = logging.LogRecord(
            "backend.test",
            logging.WARNING,
            __file__,
            1,
            "warning",
            (),
            None,
        )
        error = logging.LogRecord(
            "backend.test",
            logging.ERROR,
            __file__,
            2,
            "error",
            (),
            None,
        )

        self.assertIn("\033[33m", formatter.format(warning))
        self.assertIn("\033[31m", formatter.format(error))

    def test_http_logs_human_summaries_without_payload_values(self) -> None:
        handler = FakeRequestHandler(
            b'{"email":"person@example.com","password":"private-password"}'
        )

        with self.assertLogs("backend.utils.http", level="INFO") as logs:
            payload = read_json_object(handler, 100, request_name="Login")
            send_json(
                handler,
                {"status": "ok", "name": "Private Name"},
            )

        self.assertEqual(payload["email"], "person@example.com")
        output = "\n".join(logs.output)
        self.assertIn("Login input received (email supplied, password supplied)", output)
        self.assertIn("Backend output: Request completed: OK.", output)
        self.assertNotIn("{", output)
        self.assertNotIn("person@example.com", output)
        self.assertNotIn("private-password", output)
        self.assertNotIn("Private Name", output)

    def test_http_output_summarizes_dashboard_orders(self) -> None:
        handler = FakeRequestHandler(b"")

        with self.assertLogs("backend.utils.http", level="INFO") as logs:
            send_json(
                handler,
                {
                    "status": "ok",
                    "database": "lpvr.db",
                    "tables": [],
                    "orders": [
                        {
                            "order_id": 9,
                            "order_date": "2026-10-21",
                            "total_amount": 50.0,
                            "paid": False,
                        }
                    ],
                    "payments": [],
                },
            )

        output = "\n".join(logs.output)
        self.assertIn(
            "Dashboard loaded: 1 order, $50.00 total, 0 payment record(s). "
            "Orders: #9 $50.00, 2026-10-21, unpaid.",
            output,
        )
        self.assertNotIn("{", output)

    def test_http_status_labels_explain_cache_responses(self) -> None:
        self.assertEqual(http_status_label(200), "OK")
        self.assertEqual(http_status_label(304), "Not Modified (browser cache)")
        self.assertEqual(http_status_label(404), "Not Found")
        self.assertEqual(http_status_label(599), "Unknown status")

    def test_reads_json_object_and_rejects_non_objects(self) -> None:
        handler = FakeRequestHandler(b'{"order_id": 1}')
        self.assertEqual(read_json_object(handler, 100), {"order_id": 1})

        with self.assertRaisesRegex(HTTPRequestError, "must be an object"):
            read_json_object(FakeRequestHandler(b"[]"), 100, "Payment")

    def test_rejects_invalid_content_length_and_oversized_body(self) -> None:
        with self.assertRaisesRegex(HTTPRequestError, "Content-Length"):
            read_json_object(FakeRequestHandler(b"{}", "invalid"), 100)
        with self.assertRaisesRegex(HTTPRequestError, "request size"):
            read_json_object(FakeRequestHandler(b'{"x": 1}'), 2, "Payment")

    def test_sends_json_response_with_headers(self) -> None:
        handler = FakeRequestHandler(b"")
        send_json(handler, {"status": "ok"}, 201)

        self.assertEqual(handler.response_status, 201)
        self.assertEqual(
            handler.response_headers["Content-Type"],
            "application/json; charset=utf-8",
        )
        self.assertEqual(
            json.loads(handler.wfile.getvalue().decode("utf-8")),
            {"status": "ok"},
        )


if __name__ == "__main__":
    unittest.main()
