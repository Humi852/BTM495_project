import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.apis.event_registration_api import EventRegistrationAPI
from backend.utils.constants import StatusID
from database.sqlite_database import initialize_database


class EventRegistrationAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test.db"
        initialize_database(self.database_path)
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.executemany(
                "INSERT INTO customer (customer_id, name) VALUES (?, ?)",
                [(10, "A"), (11, "B"), (12, "C")],
            )
            connection.executemany(
                "INSERT INTO event (event_id, name, participantLimit, statusID) "
                "VALUES (?, 'Ride', ?, ?)",
                [(1, 2, None), (2, 5, StatusID.EVENT_CANCELLED)],
            )
            connection.commit()
        self.api = EventRegistrationAPI(self.database_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _rows(self) -> list[tuple[int, int]]:
        with closing(sqlite3.connect(self.database_path)) as connection:
            return connection.execute(
                "SELECT event_id, customer_id FROM event_registration "
                "ORDER BY event_id, customer_id"
            ).fetchall()

    def test_register_writes_to_event_registration_table(self) -> None:
        self.assertFalse(self.api.isFull(1).data)
        self.assertTrue(self.api.register(1, 10).success)
        self.assertEqual(self._rows(), [(1, 10)])
        self.assertEqual(self.api.listRegistrations(1).data, [10])

        # A fresh API instance sees the same data, so nothing lives in memory.
        self.assertEqual(
            EventRegistrationAPI(self.database_path).listRegistrations(1).data, [10]
        )

    def test_register_rejects_duplicates_and_enforces_the_limit(self) -> None:
        self.assertTrue(self.api.register(1, 10).success)
        self.assertEqual(
            self.api.register(1, 10).msg, "Customer is already registered."
        )
        self.assertTrue(self.api.register(1, 11).success)
        self.assertTrue(self.api.isFull(1).data)
        self.assertEqual(self.api.register(1, 12).msg, "Event is full.")
        self.assertEqual(self._rows(), [(1, 10), (1, 11)])

    def test_register_validates_event_customer_and_status(self) -> None:
        self.assertEqual(self.api.register(99, 10).msg, "Event not found.")
        self.assertEqual(self.api.register(1, 99).msg, "Customer not found.")
        self.assertEqual(
            self.api.register(1, 0).msg, "A valid customer ID is required."
        )
        self.assertFalse(self.api.register(1, "10").success)
        self.assertEqual(
            self.api.register(2, 10).msg, "Event is not open for registration."
        )
        self.assertEqual(self._rows(), [])

    def test_unregister_frees_a_spot(self) -> None:
        self.api.register(1, 10)
        self.api.register(1, 11)
        self.assertTrue(self.api.unregister(1, 10).success)
        self.assertFalse(self.api.isFull(1).data)
        self.assertEqual(self.api.unregister(1, 10).msg, "Registration not found.")
        self.assertTrue(self.api.register(1, 12).success)
        self.assertEqual(self.api.listRegistrations(1).data, [11, 12])

    def test_unknown_event_queries_return_warnings(self) -> None:
        self.assertEqual(self.api.isFull(99).msg, "Event not found.")
        self.assertEqual(self.api.listRegistrations(99).msg, "Event not found.")

    def test_deleting_an_event_removes_its_registrations(self) -> None:
        self.api.register(1, 10)
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("DELETE FROM event WHERE event_id = 1")
            connection.commit()
        self.assertEqual(self._rows(), [])


if __name__ == "__main__":
    unittest.main()
