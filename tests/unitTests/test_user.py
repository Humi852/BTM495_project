import sqlite3
import sys
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.models.user import User
from backend.services.user import UserService


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
            User(
                name="Alice",
                email="alice@example.com",
                phone="555-0100",
                address="10 Bike Lane",
            )
        )

        saved_user = self.user_service.getUser(user.userID)

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
            User(name="Morgan", email="morgan@example.com", isAdmin=True)
        )

        saved_admin = self.user_service.getUser(admin.userID)

        self.assertIsNotNone(saved_admin)
        self.assertTrue(saved_admin.isAdmin)

    def test_update_profile(self) -> None:
        user = self.user_service.createUser(
            User(name="Alice", email="alice@example.com")
        )
        user.name = "Alice Smith"
        user.phone = "555-0199"

        self.assertTrue(self.user_service.updateProfile(user))
        saved_user = self.user_service.getUser(user.userID)

        self.assertEqual(saved_user.name, "Alice Smith")
        self.assertEqual(saved_user.phone, "555-0199")

    def test_profile_requires_name_and_email(self) -> None:
        with self.assertRaisesRegex(ValueError, "Name is required"):
            self.user_service.createUser(User(name=" ", email="alice@example.com"))

        with self.assertRaisesRegex(ValueError, "Email is required"):
            self.user_service.createUser(User(name="Alice", email=" "))

    def test_profile_confirmation_helpers(self) -> None:
        self.assertTrue(
            self.user_service.validateInformation("Alice", "alice@example.com")
        )
        self.assertFalse(self.user_service.validateInformation("", "alice@example.com"))
        self.assertFalse(self.user_service.validateInformation("Alice", "invalid"))
        self.assertTrue(self.user_service.confirmInformation("YES"))
        self.assertFalse(self.user_service.confirmInformation("no"))


if __name__ == "__main__":
    unittest.main()
