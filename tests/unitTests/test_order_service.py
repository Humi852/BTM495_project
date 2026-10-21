import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.models.part import Part
from backend.models.shoppingCart import ShoppingCart
from backend.models.customer import Customer
from backend.services.order import OrderService
from backend.services.user import UserService
from database.db import initialize_database


class OrderServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "checkout.db"
        initialize_database(self.database_path)
        self.customer = UserService(self.database_path).createUser(
            Customer(name="Casey", email="casey@example.com")
        )
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                "INSERT INTO item "
                "(item_id, name, description, sellingprice, costprice, stock_quantity) "
                "VALUES (10, 'Tube', 'Road tube', 9.5, 4.0, 5)"
            )
            connection.commit()

        self.part = Part(10, "Tube", "Road tube", 8.5, "Tires", "RoadCo", 5)
        self.cart = ShoppingCart(1)
        self.cart.addItem(self.part, 2)
        self.service = OrderService(self.database_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_checkout_persists_order_lines_and_decrements_stock(self) -> None:
        order = self.service.checkout(self.cart, self.customer.customerID)

        self.assertEqual(order.orderId, 1)
        self.assertEqual(order.status, "Placed")
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
                    "SELECT item_id, quantity, unit_price FROM order_item "
                    "WHERE order_id = 1"
                ).fetchall(),
                [(10, 2, 8.5)],
            )
            self.assertEqual(
                connection.execute(
                    "SELECT stock_quantity FROM item WHERE item_id = 10"
                ).fetchone(),
                (3,),
            )

        self.assertEqual(
            self.service.checkout(self.cart, self.customer.customerID),
            "Cart is empty.",
        )

    def test_insufficient_database_stock_leaves_cart_and_data_unchanged(self) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                "UPDATE item SET stock_quantity = 1 WHERE item_id = 10"
            )
            connection.commit()

        self.assertEqual(
            self.service.checkout(self.cart, self.customer.customerID),
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
                    "SELECT stock_quantity FROM item WHERE item_id = 10"
                ).fetchone(),
                (1,),
            )

    def test_missing_database_item_does_not_create_partial_order(self) -> None:
        missing_part = Part(99, "Pump", "Mini pump", 12.0, "Tools", "RoadCo", 3)
        self.cart.addItem(missing_part)

        with self.assertRaisesRegex(ValueError, "Item 99 does not exist"):
            self.service.checkout(self.cart, self.customer.customerID)

        self.assertEqual(len(self.cart.items), 2)
        with closing(sqlite3.connect(self.database_path)) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM orders").fetchone(),
                (0,),
            )
            self.assertEqual(
                connection.execute(
                    "SELECT stock_quantity FROM item WHERE item_id = 10"
                ).fetchone(),
                (5,),
            )

    def test_database_stock_update_failure_rolls_back_order_and_lines(self) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                "CREATE TRIGGER ignore_stock_updates "
                "BEFORE UPDATE OF stock_quantity ON item "
                "BEGIN SELECT RAISE(IGNORE); END"
            )
            connection.commit()

        self.assertEqual(
            self.service.checkout(self.cart, self.customer.customerID),
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
                    "SELECT stock_quantity FROM item WHERE item_id = 10"
                ).fetchone(),
                (5,),
            )


if __name__ == "__main__":
    unittest.main()
