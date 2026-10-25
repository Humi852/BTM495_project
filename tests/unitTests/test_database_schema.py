import sqlite3
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.models.event import Event
from backend.models.order import OrderStatus
from backend.models.payment import PaymentStatus
from backend.utils.constants import DATABASE_SCHEMA_COLUMNS, DatabaseValues, StatusID


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = PROJECT_ROOT / "database" / "schema.sql"


class DatabaseSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    def tearDown(self) -> None:
        self.connection.close()

    def test_status_id_enum_matches_status_table(self) -> None:
        rows = self.connection.execute(
            "SELECT statusID, name FROM status"
        ).fetchall()
        self.assertEqual(
            {member.value: member.name for member in StatusID},
            {
                status_id: name.upper()
                for status_id, name in rows
            },
        )

    def test_all_schema_tables_are_created(self) -> None:
        tables = {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }

        self.assertEqual(
            tables,
            {
                "admin",
                "customer",
                "event",
                "event_registration",
                "appointment",
                "item",
                "inventory",
                "inventory_history",
                "shopping_cart",
                "orders",
                "order_item",
                "payment",
                "status",
            },
        )
        self.assertEqual(tables, set(DATABASE_SCHEMA_COLUMNS))

    def test_database_constants_match_schema_columns(self) -> None:
        for table, expected_columns in DATABASE_SCHEMA_COLUMNS.items():
            with self.subTest(table=table):
                actual_columns = tuple(
                    row[1]
                    for row in self.connection.execute(
                        f"PRAGMA table_info({table})"
                    )
                )
                self.assertEqual(actual_columns, expected_columns)

    def test_paid_payment_status_constant_matches_schema(self) -> None:
        self.assertEqual(
            self.connection.execute(
                "SELECT statusID FROM status WHERE name = 'Completed'"
            ).fetchone()[0],
            DatabaseValues.PAYMENT_STATUS_ID_PAID,
        )

    def test_order_status_names_exist_in_schema(self) -> None:
        statuses = {row[0] for row in self.connection.execute("SELECT name FROM status")}
        self.assertEqual(statuses, {"Pending", "Completed", "Cancelled"})
        self.assertEqual(
            self.connection.execute(
                "SELECT name FROM status WHERE statusID = ?",
                (DatabaseValues.ORDER_STATUS_ID_PENDING,),
            ).fetchone(),
            (OrderStatus.PENDING.value,),
        )
        self.assertLessEqual(
            {status.value for status in OrderStatus}, statuses
        )

    def test_event_statuses_exist_in_schema(self) -> None:
        statuses = {row[0] for row in self.connection.execute("SELECT name FROM status")}
        event = Event(1, "Ride", "Group ride", "Park", datetime(2026, 11, 1), 5)
        self.assertIn(event.status, statuses)
        event.cancel()
        self.assertIn(event.status, statuses)

    def test_primary_keys_are_defined_for_all_tables(self) -> None:
        expected_primary_keys = {
            "admin": ["admin_id"],
            "customer": ["customer_id"],
            "event": ["event_id"],
            "event_registration": ["event_id", "customer_id"],
            "appointment": ["appointment_id"],
            "item": ["item_id"],
            "inventory": ["item_id"],
            "inventory_history": ["history_id"],
            "shopping_cart": ["customer_id"],
            "orders": ["order_id"],
            "order_item": ["order_id", "item_id"],
            "payment": ["payment_id"],
            "status": ["statusID"],
        }

        for table, expected_columns in expected_primary_keys.items():
            with self.subTest(table=table):
                primary_key_columns = [
                    row[1]
                    for row in sorted(
                        (
                            column
                            for column in self.connection.execute(
                                f"PRAGMA table_info({table})"
                            )
                            if column[5] > 0
                        ),
                        key=lambda column: column[5],
                    )
                ]
                self.assertEqual(primary_key_columns, expected_columns)

    def test_foreign_keys_are_defined_for_expected_relationships(self) -> None:
        status_keys = {
            ("statusID", "status", "statusID"),
        }
        expected_foreign_keys = {
            "event": {("admin_id", "admin", "admin_id")} | status_keys,
            "event_registration": {
                ("event_id", "event", "event_id"),
                ("customer_id", "customer", "customer_id"),
            },
            "appointment": {("customer_id", "customer", "customer_id")} | status_keys,
            "orders": {("customer_id", "customer", "customer_id")} | status_keys,
            "shopping_cart": {("customer_id", "customer", "customer_id")},
            "inventory": {
                ("item_id", "item", "item_id"),
                ("admin_id", "admin", "admin_id"),
            },
            "inventory_history": {
                ("item_id", "item", "item_id"),
                ("admin_id", "admin", "admin_id"),
            },
            "order_item": {
                ("order_id", "orders", "order_id"),
                ("item_id", "item", "item_id"),
            },
            "payment": {("order_id", "orders", "order_id")} | status_keys,
        }

        for table, expected in expected_foreign_keys.items():
            with self.subTest(table=table):
                actual = {
                    (row[3], row[2], row[4])
                    for row in self.connection.execute(
                        f"PRAGMA foreign_key_list({table})"
                    )
                }
                self.assertEqual(actual, expected)

    def test_sample_records_insert_and_retrieve_across_relationships(self) -> None:
        self.connection.executescript(
            """
            INSERT INTO admin (admin_id, name, email)
                VALUES (1, 'Morgan Admin', 'admin@example.com');
            INSERT INTO customer (customer_id, name, email)
                VALUES (2, 'Casey Customer', 'customer@example.com');
            INSERT INTO event
                (event_id, admin_id, name, description, eventDateTime, participantLimit)
                VALUES (3, 1, 'Community Ride', 'Group ride', '2026-11-01', 20);
            INSERT INTO appointment
                (appointment_id, customer_id, appointmentTime, description)
                VALUES (4, 2, '2026-11-02', 'Bike tune-up');
            INSERT INTO item
                (item_id, name, description, price, category, brand)
                VALUES (5, 'Road Tube', '700c inner tube', 8.5, 'Parts', 'Generic');
            INSERT INTO inventory (item_id, quantity, admin_id) VALUES (5, 10, 1);
            INSERT INTO inventory_history
                (item_id, old_quantity, new_quantity, admin_id, reason)
                VALUES (5, NULL, 10, 1, 'Initial stock');
            INSERT INTO shopping_cart (customer_id, items_json)
                VALUES (2, '[{"item_id":5,"quantity":2,"price":8.5}]');
            INSERT INTO orders (order_id, customer_id, orderDateTime, totalAmount)
                VALUES (6, 2, '2026-11-03', 17.0);
            INSERT INTO order_item (order_id, item_id, quantity, unit_price)
                VALUES (6, 5, 2, 8.5);
            INSERT INTO payment
                (payment_id, order_id, paymentDateTime, amount, paymentMethod,
                 statusID)
                VALUES (
                    7, 6, '2026-11-03', 17.0, 'Cash',
                    2
                );
            """
        )

        self.assertEqual(
            self.connection.execute(
                "SELECT customer_id, items_json FROM shopping_cart "
                "WHERE customer_id = 2"
            ).fetchone(),
            (2, '[{"item_id":5,"quantity":2,"price":8.5}]'),
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT event.name, admin.name "
                "FROM event JOIN admin USING (admin_id) WHERE event_id = 3"
            ).fetchone(),
            ("Community Ride", "Morgan Admin"),
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT appointment.description, customer.name "
                "FROM appointment JOIN customer USING (customer_id) "
                "WHERE appointment_id = 4"
            ).fetchone(),
            ("Bike tune-up", "Casey Customer"),
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT order_item.quantity, order_item.unit_price, item.name, "
                "payment.amount FROM order_item "
                "JOIN item USING (item_id) "
                "JOIN orders USING (order_id) "
                "JOIN payment USING (order_id) WHERE orders.order_id = 6"
            ).fetchone(),
            (2, 8.5, "Road Tube", 17.0),
        )

    def test_duplicate_email_is_rejected_within_each_role_table(self) -> None:
        self.connection.execute(
            "INSERT INTO admin (name, email) VALUES (?, ?)",
            ("Morgan", "shared@example.com"),
        )
        self.connection.execute(
            "INSERT INTO customer (name, email) VALUES (?, ?)",
            ("Casey", "shared@example.com"),
        )

        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO admin (name, email) VALUES (?, ?)",
                ("Another admin", "shared@example.com"),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO customer (name, email) VALUES (?, ?)",
                ("Another customer", "shared@example.com"),
            )

    def test_shopping_cart_rejects_invalid_json(self) -> None:
        self.connection.execute(
            "INSERT INTO customer (customer_id, name) VALUES (1, 'Casey')"
        )

        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO shopping_cart (customer_id, items_json) "
                "VALUES (1, 'not-json')"
            )

    def test_invalid_foreign_key_references_are_rejected(self) -> None:
        invalid_inserts = (
            (
                "INSERT INTO event (name, admin_id) VALUES ('Invalid event', 999)",
                (),
            ),
            (
                "INSERT INTO appointment (customer_id) VALUES (999)",
                (),
            ),
            (
                "INSERT INTO shopping_cart (customer_id, items_json) "
                "VALUES (999, '[]')",
                (),
            ),
            (
                "INSERT INTO orders (customer_id) VALUES (999)",
                (),
            ),
            (
                "INSERT INTO order_item (order_id, item_id, quantity, unit_price) "
                "VALUES (999, 999, 1, 1.0)",
                (),
            ),
            (
                "INSERT INTO payment "
                "(order_id, paymentDateTime, amount, paymentMethod, statusID) "
                "VALUES (999, '2026-11-03', 1.0, 'Cash', 0)",
                (),
            ),
        )

        for statement, parameters in invalid_inserts:
            with self.subTest(statement=statement):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.connection.execute(statement, parameters)
                self.connection.rollback()

    def test_status_must_exist_in_status_table(self) -> None:
        self.connection.executescript(
            """
            INSERT INTO admin (admin_id, name) VALUES (1, 'Morgan Admin');
            INSERT INTO customer (customer_id, name) VALUES (2, 'Casey Customer');
            """
        )
        invalid_inserts = (
            "INSERT INTO event (admin_id, name, statusID) VALUES (1, 'Wrong', 99)",
            "INSERT INTO appointment (customer_id, statusID) VALUES (2, 99)",
            "INSERT INTO orders (customer_id, statusID) VALUES (2, 99)",
        )
        for statement in invalid_inserts:
            with self.subTest(statement=statement):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.connection.execute(statement)
    def test_event_registration_tracks_unique_customer_per_event(self) -> None:
        self.connection.executescript(
            """
            INSERT INTO admin (admin_id, name) VALUES (1, 'Morgan Admin');
            INSERT INTO customer (customer_id, name) VALUES (2, 'Casey Customer');
            INSERT INTO event (event_id, admin_id, name) VALUES (3, 1, 'Community Ride');
            INSERT INTO event_registration (event_id, customer_id) VALUES (3, 2);
            """
        )
        invalid_inserts = (
            "INSERT INTO event_registration (event_id, customer_id) VALUES (3, 2)",
            "INSERT INTO event_registration (event_id, customer_id) VALUES (999, 2)",
            "INSERT INTO event_registration (event_id, customer_id) VALUES (3, 999)",
            "INSERT INTO event_registration (event_id, customer_id) VALUES (3, NULL)",
        )
        for statement in invalid_inserts:
            with self.subTest(statement=statement):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.connection.execute(statement)

        self.connection.execute("DELETE FROM event WHERE event_id = 3")
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM event_registration"
            ).fetchone()[0],
            0,
        )

    def test_order_item_rejects_nonpositive_quantity_and_negative_price(self) -> None:
        self.connection.executescript(
            """
            INSERT INTO customer (customer_id, name) VALUES (1, 'Casey');
            INSERT INTO item (item_id, name) VALUES (1, 'Road Tube');
            INSERT INTO orders (order_id, customer_id) VALUES (1, 1);
            """
        )

        invalid_lines = ((0, 8.5), (-1, 8.5), (1, -0.01))
        for quantity, unit_price in invalid_lines:
            with self.subTest(quantity=quantity, unit_price=unit_price):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.connection.execute(
                        "INSERT INTO order_item "
                        "(order_id, item_id, quantity, unit_price) "
                        "VALUES (1, 1, ?, ?)",
                        (quantity, unit_price),
                    )
                self.connection.rollback()
