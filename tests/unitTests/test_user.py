import sqlite3
import sys
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.models.user import Admin, Customer
from backend.services.user import UserService
from database.db import initialize_database
from database.db import initialize_database


class UserServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "users.db"
        schema_path = Path(__file__).resolve().parents[2] / "database" / "schema.sql"
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.executescript(schema_path.read_text(encoding="utf-8"))
        self.user_service = UserService(self.database_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_create_and_get_customer_profile(self) -> None:
        user = self.user_service.createUser(
            Customer(
                name="Alice",
                email="alice@example.com",
                phone="555-0100",
                address="10 Bike Lane",
            )
        )

        saved_user = self.user_service.getUser(user.userID, Customer)

        self.assertIsNotNone(user.userID)
        self.assertIsNotNone(saved_user)
        self.assertEqual(saved_user.userID, user.userID)
        self.assertEqual(saved_user.name, "Alice")
        self.assertEqual(saved_user.email, "alice@example.com")
        self.assertEqual(saved_user.phone, "555-0100")
        self.assertEqual(saved_user.address, "10 Bike Lane")
        self.assertFalse(saved_user.isAdmin)

    def test_create_and_get_admin_profile(self) -> None:
        admin = self.user_service.createUser(
            Admin(
                name="Morgan",
                email="morgan@example.com",
                password_hash="test-hash",
            )
        )

        saved_admin = self.user_service.getUser(admin.userID, Admin)

        self.assertIsNotNone(saved_admin)
        self.assertTrue(saved_admin.isAdmin)
        self.assertEqual(saved_admin.password_hash, "test-hash")

    def test_update_profile_persists_password_hash(self) -> None:
        user = self.user_service.createUser(
            Customer(name="Alice", email="alice@example.com")
        )
        user.password_hash = "updated-test-hash"

        self.assertTrue(self.user_service.updateProfile(user))
        saved_user = self.user_service.getUser(user.userID, Customer)

        self.assertEqual(saved_user.password_hash, "updated-test-hash")

    def test_update_profile(self) -> None:
        user = self.user_service.createUser(
            Customer(name="Alice", email="alice@example.com")
        )
        user.name = "Alice Smith"
        user.phone = "555-0199"

        self.assertTrue(self.user_service.updateProfile(user))
        saved_user = self.user_service.getUser(user.userID, Customer)

        self.assertEqual(saved_user.name, "Alice Smith")
        self.assertEqual(saved_user.phone, "555-0199")

    def test_profile_requires_name_and_email(self) -> None:
        with self.assertRaisesRegex(ValueError, "Name is required"):
            self.user_service.createUser(
                Customer(name=" ", email="alice@example.com")
            )

        with self.assertRaisesRegex(ValueError, "Email is required"):
            self.user_service.createUser(Customer(name="Alice", email=" "))

        with self.assertRaisesRegex(ValueError, "Email must contain"):
            self.user_service.createUser(Customer(name="Alice", email="invalid"))

    def test_update_profile_uses_the_same_email_validation(self) -> None:
        user = self.user_service.createUser(
            Customer(name="Alice", email="alice@example.com")
        )
        user.email = "invalid"

        with self.assertRaisesRegex(ValueError, "Email must contain"):
            self.user_service.updateProfile(user)

        saved_user = self.user_service.getUser(user.userID, Customer)
        self.assertEqual(saved_user.email, "alice@example.com")

    def test_profile_confirmation_helpers(self) -> None:
        self.assertTrue(
            self.user_service.validateInformation("Alice", "alice@example.com")
        )
        self.assertFalse(self.user_service.validateInformation("", "alice@example.com"))
        self.assertFalse(self.user_service.validateInformation("Alice", "invalid"))
        self.assertTrue(self.user_service.confirmInformation("YES"))
        self.assertFalse(self.user_service.confirmInformation("no"))

    def test_role_emails_remain_unique_across_tables(self) -> None:
        self.user_service.createUser(Admin(name="Morgan", email="same@example.com"))

        self.user_service.createUser(
            Customer(name="Taylor", email="same@example.com")
        )

    def test_email_is_unique_within_each_role_table(self) -> None:
        admin = self.user_service.createUser(
            Admin(name="Morgan", email="admin@example.com")
        )
        customer = self.user_service.createUser(
            Customer(name="Taylor", email="customer@example.com")
        )

        with self.assertRaises(sqlite3.IntegrityError):
            self.user_service.createUser(
                Admin(name="Another Admin", email=admin.email)
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.user_service.createUser(
                Customer(name="Another Customer", email=customer.email)
            )

    def test_schema_initialization_removes_legacy_cross_table_triggers(self) -> None:
        database_path = Path(self.temp_dir.name) / "existing.db"
        initialize_database(database_path)
        with closing(sqlite3.connect(database_path)) as connection:
            connection.executescript(
                """
                CREATE TRIGGER admin_email_insert_unique
                BEFORE INSERT ON admin
                WHEN NEW.email IS NOT NULL AND EXISTS (
                    SELECT 1 FROM customer WHERE email = NEW.email
                )
                BEGIN
                    SELECT RAISE(ABORT, 'email already belongs to another account');
                END;
                CREATE TRIGGER admin_email_update_unique
                BEFORE UPDATE OF email ON admin
                WHEN NEW.email IS NOT NULL AND EXISTS (
                    SELECT 1 FROM customer WHERE email = NEW.email
                )
                BEGIN
                    SELECT RAISE(ABORT, 'email already belongs to another account');
                END;
                CREATE TRIGGER customer_email_insert_unique
                BEFORE INSERT ON customer
                WHEN NEW.email IS NOT NULL AND EXISTS (
                    SELECT 1 FROM admin WHERE email = NEW.email
                )
                BEGIN
                    SELECT RAISE(ABORT, 'email already belongs to another account');
                END;
                CREATE TRIGGER customer_email_update_unique
                BEFORE UPDATE OF email ON customer
                WHEN NEW.email IS NOT NULL AND EXISTS (
                    SELECT 1 FROM admin WHERE email = NEW.email
                )
                BEGIN
                    SELECT RAISE(ABORT, 'email already belongs to another account');
                END;
                INSERT INTO customer (name, email) VALUES ('Taylor', 'shared@example.com');
                """
            )

        initialize_database(database_path)

        with closing(sqlite3.connect(database_path)) as connection:
            triggers = connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'trigger' AND name LIKE '%email%unique'"
            ).fetchall()
            self.assertEqual(triggers, [])
            connection.execute(
                "INSERT INTO admin (name, email) VALUES (?, ?)",
                ("Morgan", "shared@example.com"),
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM customer").fetchone()[0],
                1,
            )

    def test_database_initialization_creates_schema_idempotently(self) -> None:
        new_path = Path(self.temp_dir.name) / "new.db"

        initialize_database(new_path)
        initialize_database(new_path)

        with closing(sqlite3.connect(new_path)) as connection:
            table_names = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            self.assertIn("admin", table_names)
            self.assertIn("customer", table_names)
            self.assertIn("order_item", table_names)
            self.assertNotIn("user", table_names)
            self.assertNotIn("schema_migrations", table_names)


if __name__ == "__main__":
    unittest.main()
