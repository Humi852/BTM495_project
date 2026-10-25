import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.models.item import Item
from backend.apis.shopping_cart_api import ShoppingCartAPI
from backend.models.customer import Customer
from backend.apis.order_api import OrderService
from backend.apis.profile_api import ManageProfile
from database.sqlite_database import initialize_database


class OrderServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "checkout.db"
        initialize_database(self.database_path)
        self.customer = ManageProfile(self.database_path).createAccount(
            Customer(name="Casey", email="casey@example.com"),
            "order-password",
        )
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                "INSERT INTO item "
                "(item_id, name, description, price, category, brand) "
                "VALUES (10, 'Tube', 'Road tube', 9.5, 'Parts', 'Generic')"
            )
            connection.execute(
                "INSERT INTO inventory (item_id, quantity) VALUES (10, 5)"
            )
            connection.commit()

        self.part = Item(10, "Tube", "Road tube", 8.5, "Tires", "RoadCo", 5)
        self.cart_api = ShoppingCartAPI(self.database_path)
        self.cart = self.cart_api.loadCart(self.customer.customerID)
        self.cart_api.addItem(self.cart, self.part, 2)
        self.service = OrderService(self.database_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_checkout_persists_order_lines_and_decrements_stock(self) -> None:
        result = self.service.checkout(self.cart, self.customer.customerID)
        order = result.data

        self.assertTrue(result.success)
        self.assertEqual(order.orderId, 1)
        self.assertEqual(order.status, "Pending")
        self.assertEqual(order.getTotalPrice(), 17.0)
        self.assertEqual(self.cart.items, {})
        self.assertEqual(self.part.checkStock(), 3)
        with closing(sqlite3.connect(self.database_path)) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT customer_id, totalAmount FROM orders WHERE order_id = 1"
                ).fetchone(),
                (self.customer.customerID, 17.0),
            )
            self.assertEqual(
                connection.execute(
                    "SELECT status.name FROM orders "
                    "JOIN status USING (statusID, category) WHERE order_id = 1"
                ).fetchone(),
                (order.status,),
            )
            self.assertEqual(
                connection.execute(
                    "SELECT item_id, quantity, unit_price FROM order_item "
                    "WHERE order_id = 1"
                ).fetchall(),
                [(10, 2, 8.5)],
            )
            self.assertEqual(
                connection.execute(
                    "SELECT quantity FROM inventory WHERE item_id = 10"
                ).fetchone(),
                (3,),
            )
            self.assertEqual(
                connection.execute(
                    "SELECT old_quantity, new_quantity, admin_id, reason "
                    "FROM inventory_history WHERE item_id = 10"
                ).fetchall(),
                [(5, 3, None, "Checkout order 1")],
            )
            self.assertEqual(
                connection.execute(
                    "SELECT items_json FROM shopping_cart WHERE customer_id = ?",
                    (self.customer.customerID,),
                ).fetchone(),
                ("[]",),
            )

        self.assertEqual(
            self.service.checkout(self.cart, self.customer.customerID).msg,
            "Cart is empty.",
        )

    def test_checkout_rejects_cart_not_stored_in_order_database(self) -> None:
        other_database_path = Path(self.temp_dir.name) / "other.db"
        initialize_database(other_database_path)
        with closing(sqlite3.connect(other_database_path)) as connection:
            connection.execute(
                "INSERT INTO customer (customer_id, name) VALUES (?, 'Casey')",
                (self.customer.customerID,),
            )
            connection.commit()
        other_service = OrderService(other_database_path)

        with self.assertRaisesRegex(ValueError, "(?i)shopping cart.*does not exist"):
            other_service.checkout(self.cart, self.customer.customerID)

    def test_insufficient_database_stock_leaves_cart_and_data_unchanged(self) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                "UPDATE inventory SET quantity = 1 WHERE item_id = 10"
            )
            connection.commit()

        self.assertEqual(
            self.service.checkout(self.cart, self.customer.customerID).msg,
            "Item out of stock.",
        )
        self.assertEqual(self.cart.items[10].quantity, 2)
        self.assertEqual(self.part.checkStock(), 5)
        with closing(sqlite3.connect(self.database_path)) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM orders").fetchone(),
                (0,),
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM order_item").fetchone(),
                (0,),
            )
            self.assertEqual(
                connection.execute(
                    "SELECT quantity FROM inventory WHERE item_id = 10"
                ).fetchone(),
                (1,),
            )
            self.assertEqual(
                connection.execute(
                    "SELECT items_json FROM shopping_cart WHERE customer_id = ?",
                    (self.customer.customerID,),
                ).fetchone(),
                ('[{"item_id":10,"quantity":2,"price":8.5}]',),
            )

    def test_missing_database_item_does_not_create_partial_order(self) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute("DELETE FROM item WHERE item_id = 10")
            connection.commit()

        with self.assertRaisesRegex(ValueError, "Item 10 does not exist"):
            self.service.checkout(self.cart, self.customer.customerID)

        self.assertEqual(len(self.cart.items), 1)
        with closing(sqlite3.connect(self.database_path)) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM orders").fetchone(),
                (0,),
            )
            self.assertEqual(
                connection.execute(
                    "SELECT items_json FROM shopping_cart WHERE customer_id = ?",
                    (self.customer.customerID,),
                ).fetchone(),
                ('[{"item_id":10,"quantity":2,"price":8.5}]',),
            )

    def test_database_stock_update_failure_rolls_back_order_and_lines(self) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                "CREATE TRIGGER ignore_stock_updates "
                "BEFORE UPDATE OF quantity ON inventory "
                "BEGIN SELECT RAISE(IGNORE); END"
            )
            connection.commit()

        self.assertEqual(
            self.service.checkout(self.cart, self.customer.customerID).msg,
            "Item out of stock.",
        )
        self.assertEqual(self.cart.items[10].quantity, 2)
        self.assertEqual(self.part.checkStock(), 5)
        with closing(sqlite3.connect(self.database_path)) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM orders").fetchone(),
                (0,),
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM order_item").fetchone(),
                (0,),
            )
            self.assertEqual(
                connection.execute(
                    "SELECT quantity FROM inventory WHERE item_id = 10"
                ).fetchone(),
                (5,),
            )


if __name__ == "__main__":
    unittest.main()
