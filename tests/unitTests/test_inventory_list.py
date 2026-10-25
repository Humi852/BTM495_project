import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.apis.inventory_list_api import InventoryList, Item
from database.sqlite_database import initialize_database


class InventoryListTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test.db"
        initialize_database(self.database_path)
        self.inventory = InventoryList(self.database_path)
        self.part = Item(10, "Tube", "Inner tube", 8.5, "Tires", "RoadCo", 5)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _row(self, item_id: int = 10):
        with closing(sqlite3.connect(self.database_path)) as connection:
            return connection.execute(
                "SELECT i.name, i.price, inv.quantity FROM item i "
                "LEFT JOIN inventory inv USING (item_id) WHERE i.item_id = ?",
                (item_id,),
            ).fetchone()

    def _history(self, item_id: int = 10):
        return [
            (h["oldQuantity"], h["newQuantity"], h["adminId"], h["reason"])
            for h in self.inventory.listHistory(item_id).data
        ]

    def test_stock_is_a_standalone_inventory_row_with_history(self) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute("INSERT INTO admin (admin_id, name) VALUES (1, 'Morgan')")
            connection.commit()
        self.inventory.addItem(self.part, adminId=1)
        self.inventory.updateItem(10, stockQuantity=3, adminId=1, reason="Cycle count")
        self.inventory.updateItem(10, stockQuantity=None)
        self.assertEqual(
            self._history(),
            [
                (None, 5, 1, "Item added"),
                (5, 3, 1, "Cycle count"),
                (3, None, None, None),
            ],
        )
        self.assertEqual(self.inventory.updateItem(10, price=1.0, adminId=1).data["price"], (8.5, 1.0))
        self.assertEqual(len(self._history()), 3)  # price change is not a stock change

    def test_unknown_admin_is_rejected_without_changes(self) -> None:
        self.inventory.addItem(self.part)
        self.assertEqual(
            self.inventory.updateItem(10, stockQuantity=1, adminId=99).msg, "Unknown admin."
        )
        self.assertEqual(self._row()[2], 5)
        self.assertEqual(len(self._history()), 1)

    def test_removing_an_item_removes_its_inventory(self) -> None:
        self.inventory.addItem(self.part)
        self.inventory.removeItem(10)
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM inventory").fetchone(), (0,))

    def test_old_database_stock_is_migrated_to_inventory(self) -> None:
        legacy = Path(self.temp_dir.name) / "legacy.db"
        with closing(sqlite3.connect(legacy)) as connection:
            connection.executescript(
                "CREATE TABLE item (item_id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
                "description TEXT, price REAL, category TEXT, brand TEXT, stock_quantity INTEGER);"
                "INSERT INTO item (item_id, name, stock_quantity) VALUES (1, 'A', 4), (2, 'B', NULL);"
            )
            connection.commit()
        initialize_database(legacy)
        initialize_database(legacy)  # idempotent
        migrated = InventoryList(legacy)
        self.assertEqual([i.stockQuantity for i in migrated.listItems().data], [4, None])
        self.assertEqual(migrated.listHistory(1).data[0]["reason"], "Migrated from item.stock_quantity")
        with closing(sqlite3.connect(legacy)) as connection:
            columns = [row[1] for row in connection.execute("PRAGMA table_info(item)")]
        self.assertNotIn("stock_quantity", columns)

    def test_add_find_and_list_items_use_the_item_table(self) -> None:
        self.assertEqual(self.inventory.listItems().data, [])
        self.assertEqual(self.inventory.findItem(10).msg, "Item not found.")

        self.assertEqual(self.inventory.addItem(self.part).msg, "Item added successfully.")
        self.assertEqual(self._row(), ("Tube", 8.5, 5))
        self.assertEqual(self.inventory.addItem(self.part).msg, "Item already exists.")

        # A new instance reads the same data, so nothing lives in memory.
        reloaded = InventoryList(self.database_path)
        found = reloaded.findItem(10).data
        self.assertEqual((found.name, found.price, found.stockQuantity), ("Tube", 8.5, 5))
        self.assertEqual([item.itemId for item in reloaded.listItems().data], [10])

    def test_add_rejects_invalid_items(self) -> None:
        for bad in (
            Item(0, "Tube", "", 1.0),
            Item(11, " ", "", 1.0),
            Item(11, "Tube", "", -1.0),
            Item(11, "Tube", "", 1.0, stockQuantity=-1),
        ):
            self.assertEqual(self.inventory.addItem(bad).msg, "Invalid item information.")
        self.assertEqual(self.inventory.listItems().data, [])

    def test_untracked_stock_is_stored_as_null(self) -> None:
        self.inventory.addItem(Item(12, "Tune-up", "Service", 40.0))
        self.assertIsNone(self._row(12)[2])
        self.assertIsNone(self.inventory.findItem(12).data.stockQuantity)

    def test_update_applies_only_real_differences(self) -> None:
        self.inventory.addItem(self.part)
        result = self.inventory.updateItem(10, price=9.0, stockQuantity=3, name="Tube")
        self.assertTrue(result.success)
        self.assertEqual(result.data, {"price": (8.5, 9.0), "stockQuantity": (5, 3)})
        self.assertEqual(self._row(), ("Tube", 9.0, 3))

        self.assertEqual(self.inventory.updateItem(10, price=9.0).msg, "No changes detected.")
        self.assertEqual(self.inventory.updateItem(10).msg, "No changes detected.")
        self.assertTrue(self.inventory.updateItem(10, stockQuantity=None).success)
        self.assertIsNone(self._row()[2])

    def test_update_is_all_or_nothing(self) -> None:
        self.inventory.addItem(self.part)
        self.assertEqual(
            self.inventory.updateItem(10, price=1.0, stockQuantity=-1).msg,
            "Invalid value for: stockQuantity.",
        )
        self.assertEqual(
            self.inventory.updateItem(10, stock_quantity=5).msg, "Cannot update: stock_quantity."
        )
        self.assertFalse(self.inventory.updateItem(10, price=True).success)
        self.assertEqual(self.inventory.updateItem(99, price=1.0).msg, "Item not found.")
        self.assertEqual(self._row(), ("Tube", 8.5, 5))

    def test_remove_item(self) -> None:
        self.inventory.addItem(self.part)
        removed = self.inventory.removeItem(10)
        self.assertEqual(removed.data.itemId, 10)
        self.assertIsNone(self._row())
        self.assertEqual(self.inventory.removeItem(10).msg, "Item not found.")

    def test_remove_is_blocked_when_orders_use_the_item(self) -> None:
        self.inventory.addItem(self.part)
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute("INSERT INTO customer (customer_id, name) VALUES (1, 'A')")
            connection.execute("INSERT INTO orders (order_id, customer_id) VALUES (1, 1)")
            connection.execute(
                "INSERT INTO order_item (order_id, item_id, quantity, unit_price) "
                "VALUES (1, 10, 1, 8.5)"
            )
            connection.commit()
        self.assertEqual(
            self.inventory.removeItem(10).msg, "Item is used by existing orders."
        )
        self.assertIsNotNone(self._row())


if __name__ == "__main__":
    unittest.main()
