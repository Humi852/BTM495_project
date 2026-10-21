import sqlite3
import sys
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.models.admin import Admin
from backend.models.customer import Customer
from backend.models.user import User
from backend.apis.profile_api import ManageProfile
from database.sqlite_database import initialize_database


class ManageProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "users.db"
        schema_path = Path(__file__).resolve().parents[2] / "database" / "schema.sql"
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.executescript(schema_path.read_text(encoding="utf-8"))
        self.profile_manager = ManageProfile(self.database_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def create_profile(self, user: User) -> User:
        return self.profile_manager.createAccount(user, "test-password")

    def test_create_and_get_customer_profile(self) -> None:
        user = self.create_profile(
            Customer(
                name="Alice",
                email="alice@example.com",
                phone="555-0100",
                address="10 Bike Lane",
            )
        )

        saved_user = self.profile_manager.login(user.email, "test-password")

        self.assertIsNotNone(user.customerID)
        self.assertIsNotNone(saved_user)
        self.assertEqual(saved_user.customerID, user.customerID)
        self.assertEqual(saved_user.name, "Alice")
        self.assertEqual(saved_user.email, "alice@example.com")
        self.assertEqual(saved_user.phone, "555-0100")
        self.assertEqual(saved_user.address, "10 Bike Lane")
        self.assertFalse(saved_user.isAdmin)

    def test_create_account_and_login_find_matching_role(self) -> None:
        customer = self.profile_manager.createAccount(
            Customer(name="Alice", email="alice@example.com"),
            "correct-horse",
        )
        admin = self.profile_manager.createAccount(
            Admin(name="Morgan", email="alice@example.com"),
            "admin-password",
        )

        self.assertNotEqual(customer.password_hash, "correct-horse")
        self.assertTrue(customer.password_hash.startswith("pbkdf2_sha256$"))
        logged_in = self.profile_manager.login("alice@example.com", "correct-horse")
        self.assertIsInstance(logged_in, Customer)
        self.assertEqual(logged_in.customerID, customer.customerID)
        logged_in_admin = self.profile_manager.login(
            "alice@example.com", "admin-password"
        )
        self.assertIsInstance(logged_in_admin, Admin)
        self.assertEqual(logged_in_admin.adminID, admin.adminID)
        self.assertIsNone(
            self.profile_manager.login("alice@example.com", "wrong-password")
        )

    def test_login_rejects_identical_credentials_for_both_roles(self) -> None:
        self.profile_manager.createAccount(
            Customer(name="Alice", email="shared@example.com"),
            "shared-password",
        )
        self.profile_manager.createAccount(
            Admin(name="Morgan", email="shared@example.com"),
            "shared-password",
        )

        self.assertIsNone(
            self.profile_manager.login("shared@example.com", "shared-password")
        )

    def test_create_account_rejects_short_password(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 8 characters"):
            self.profile_manager.createAccount(
                Customer(name="Alice", email="alice@example.com"),
                "short",
            )

    def test_email_and_password_validation_methods(self) -> None:
        self.assertTrue(self.profile_manager.validateInformation("Alice", "alice@example.com"))
        self.assertFalse(self.profile_manager.validateInformation("Alice", "alice@localhost"))
        self.assertFalse(self.profile_manager.validateInformation("Alice", "alice@@example.com"))
        self.assertTrue(self.profile_manager.validatePassword("12345678"))
        self.assertFalse(self.profile_manager.validatePassword("1234567"))

    def test_update_profile_changes_name(self) -> None:
        customer = self.create_profile(
            Customer(name="Alice", email="alice@example.com")
        )
        customer.name = "Alice Updated"

        self.assertTrue(self.profile_manager.updateProfile(customer))
        updated = self.profile_manager.login(customer.email, "test-password")
        self.assertEqual(updated.name, "Alice Updated")

    def test_create_and_get_admin_profile(self) -> None:
        admin = self.create_profile(
            Admin(
                name="Morgan",
                email="morgan@example.com",
                phone="555-0101",
                address="1 Admin Way",
            )
        )

        saved_admin = self.profile_manager.login(admin.email, "test-password")

        self.assertIsNotNone(saved_admin)
        self.assertEqual(saved_admin.adminID, admin.adminID)
        self.assertEqual(saved_admin.name, "Morgan")
        self.assertEqual(saved_admin.email, "morgan@example.com")
        self.assertEqual(saved_admin.phone, "555-0101")
        self.assertEqual(saved_admin.address, "1 Admin Way")
        self.assertTrue(saved_admin.isAdmin)
        self.assertTrue(saved_admin.password_hash.startswith("pbkdf2_sha256$"))

    def test_update_profile_persists_password_hash(self) -> None:
        user = self.create_profile(
            Customer(name="Alice", email="alice@example.com")
        )
        user.password_hash = "updated-test-hash"

        self.assertTrue(self.profile_manager.updateProfile(user))
        with closing(sqlite3.connect(self.database_path)) as connection:
            saved_hash = connection.execute(
                "SELECT password_hash FROM customer WHERE customer_id = ?",
                (user.customerID,),
            ).fetchone()[0]
        self.assertEqual(saved_hash, "updated-test-hash")

    def test_update_profile_changes_name_and_phone(self) -> None:
        user = self.create_profile(
            Customer(name="Alice", email="alice@example.com")
        )
        user.name = "Alice Smith"
        user.phone = "555-0199"

        self.assertTrue(self.profile_manager.updateProfile(user))
        saved_user = self.profile_manager.login(user.email, "test-password")

        self.assertEqual(saved_user.name, "Alice Smith")
        self.assertEqual(saved_user.phone, "555-0199")

    def test_profile_requires_name_and_email(self) -> None:
        with self.assertRaisesRegex(ValueError, "Name is required"):
            self.profile_manager.createAccount(
                Customer(name=" ", email="alice@example.com"), "test-password"
            )

        with self.assertRaisesRegex(ValueError, "Email is required"):
            self.profile_manager.createAccount(
                Customer(name="Alice", email=" "), "test-password"
            )

        with self.assertRaisesRegex(ValueError, "Email must contain"):
            self.profile_manager.createAccount(
                Customer(name="Alice", email="invalid"), "test-password"
            )

    def test_update_profile_uses_the_same_email_validation(self) -> None:
        user = self.create_profile(
            Customer(name="Alice", email="alice@example.com")
        )
        user.email = "invalid"

        with self.assertRaisesRegex(ValueError, "Email must contain"):
            self.profile_manager.updateProfile(user)

        saved_user = self.profile_manager.login("alice@example.com", "test-password")
        self.assertEqual(saved_user.email, "alice@example.com")

    def test_profile_confirmation_helpers(self) -> None:
        self.assertTrue(
            self.profile_manager.validateInformation("Alice", "alice@example.com")
        )
        self.assertFalse(self.profile_manager.validateInformation("", "alice@example.com"))
        self.assertFalse(self.profile_manager.validateInformation("Alice", "invalid"))
        self.assertTrue(self.profile_manager.confirmInformation("YES"))
        self.assertFalse(self.profile_manager.confirmInformation("no"))

    def test_role_emails_remain_unique_across_tables(self) -> None:
        self.create_profile(Admin(name="Morgan", email="same@example.com"))

        self.create_profile(Customer(name="Taylor", email="same@example.com"))

    def test_email_is_unique_within_each_role_table(self) -> None:
        admin = self.create_profile(
            Admin(name="Morgan", email="admin@example.com")
        )
        customer = self.create_profile(
            Customer(name="Taylor", email="customer@example.com")
        )

        with self.assertRaises(sqlite3.IntegrityError):
            self.create_profile(
                Admin(name="Another Admin", email=admin.email)
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_profile(
                Customer(name="Another Customer", email=customer.email)
            )

    def test_only_requested_operations_are_public(self) -> None:
        public_methods = {
            name
            for name in dir(ManageProfile)
            if not name.startswith("_") and callable(getattr(ManageProfile, name))
        }
        self.assertEqual(
            public_methods,
            {
                "createAccount",
                "login",
                "updateProfile",
                "validateInformation",
                "validatePassword",
                "confirmInformation",
            },
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
