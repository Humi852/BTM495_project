import sqlite3
from contextlib import closing
from pathlib import Path

from backend.models.order import Order
from backend.models.shoppingCart import ShoppingCart
from database.db import DB_PATH


class OrderService:
    def __init__(self, database_path: str | Path = DB_PATH) -> None:
        self.databasePath = Path(database_path)

    def checkout(self, cart: ShoppingCart, customerID: int) -> Order | str:
        if not cart.items:
            return "Cart is empty."
        stock_error = cart._stockError()
        if stock_error is not None:
            return stock_error

        total_amount = cart.calculateTotal()
        with closing(sqlite3.connect(self.databasePath)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
            customer = connection.execute(
                "SELECT 1 FROM customer WHERE customer_id = ?",
                (customerID,),
            ).fetchone()
            if customer is None:
                raise ValueError(f"Customer {customerID} does not exist.")

            database_items: dict[int, int | None] = {}
            for cart_item in cart.items.values():
                item_id = cart_item.item.itemId
                row = connection.execute(
                    "SELECT stock_quantity FROM item WHERE item_id = ?",
                    (item_id,),
                ).fetchone()
                if row is None:
                    raise ValueError(f"Item {item_id} does not exist.")
                if row[0] is not None and cart_item.quantity > row[0]:
                    connection.rollback()
                    return "Item out of stock."
                database_items[item_id] = row[0]

            cursor = connection.execute(
                "INSERT INTO orders (customer_id, orderDateTime, totalAmount) "
                "VALUES (?, datetime('now'), ?)",
                (customerID, total_amount),
            )
            order_id = cursor.lastrowid

            for item_id, cart_item in cart.items.items():
                connection.execute(
                    "INSERT INTO order_item (order_id, item_id, quantity, unit_price) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        order_id,
                        item_id,
                        cart_item.quantity,
                        cart_item.item.getPrice(),
                    ),
                )
                database_stock = database_items[item_id]
                if database_stock is not None:
                    cursor = connection.execute(
                        "UPDATE item SET stock_quantity = stock_quantity - ? "
                        "WHERE item_id = ? AND stock_quantity >= ?",
                        (cart_item.quantity, item_id, cart_item.quantity),
                    )
                    if cursor.rowcount != 1:
                        connection.rollback()
                        return "Item out of stock."

            connection.commit()

        order = Order(order_id, total_amount)
        order.placeOrder()
        return cart._completeCheckout(order)
