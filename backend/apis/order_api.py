from pathlib import Path

from backend.apis.shopping_cart_api import ShoppingCartAPI
from backend.models.order import Order
from backend.models.shopping_cart import ShoppingCart
from backend.utils.constants import DatabaseColumns, DatabaseTables
from backend.utils.sqlite import SQLiteQuery
from backend.utils.response import Response
from database.sqlite_database import DB_PATH


class OrderService:
    def __init__(self, database_path: str | Path = DB_PATH) -> None:
        self.database = SQLiteQuery(database_path)

    def checkout(self, cart: ShoppingCart, customerID: int) -> Response:
        if cart.customerID != customerID:
            raise ValueError("Shopping cart does not belong to this customer.")
        if not cart.items:
            return Response.warning("Cart is empty.")
        stock_error = cart._stockError()
        if not stock_error.success:
            return stock_error

        total_amount = cart.calculateTotal()
        with self.database.transaction(immediate=True) as database:
            customer = database.fetch_one(
                f"SELECT 1 FROM {DatabaseTables.CUSTOMER} "
                f"WHERE {DatabaseColumns.CUSTOMER_ID} = ?",
                (customerID,),
            )
            if customer is None:
                raise ValueError(f"Customer {customerID} does not exist.")
            ShoppingCartAPI.verifyInTransaction(database, cart)

            database_items: dict[int, int | None] = {}
            for cart_item in cart.items.values():
                item_id = cart_item.item.itemId
                row = database.fetch_one(
                    f"SELECT {DatabaseColumns.STOCK_QUANTITY} "
                    f"FROM {DatabaseTables.ITEM} WHERE {DatabaseColumns.ITEM_ID} = ?",
                    (item_id,),
                )
                if row is None:
                    raise ValueError(f"Item {item_id} does not exist.")
                if row[0] is not None and cart_item.quantity > row[0]:
                    database.rollback()
                    return Response.warning("Item out of stock.")
                database_items[item_id] = row[0]

            result = database.execute(
                f"INSERT INTO {DatabaseTables.ORDERS} "
                f"({DatabaseColumns.CUSTOMER_ID}, {DatabaseColumns.ORDER_DATE_TIME}, "
                f"{DatabaseColumns.TOTAL_AMOUNT}) "
                "VALUES (?, datetime('now'), ?)",
                (customerID, total_amount),
            )
            order_id = result.lastrowid

            for item_id, cart_item in cart.items.items():
                database.execute(
                    f"INSERT INTO {DatabaseTables.ORDER_ITEM} "
                    f"({DatabaseColumns.ORDER_ID}, {DatabaseColumns.ITEM_ID}, "
                    f"{DatabaseColumns.QUANTITY}, {DatabaseColumns.UNIT_PRICE}) "
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
                    result = database.execute(
                        f"UPDATE {DatabaseTables.ITEM} "
                        f"SET {DatabaseColumns.STOCK_QUANTITY} = "
                        f"{DatabaseColumns.STOCK_QUANTITY} - ? "
                        f"WHERE {DatabaseColumns.ITEM_ID} = ? "
                        f"AND {DatabaseColumns.STOCK_QUANTITY} >= ?",
                        (cart_item.quantity, item_id, cart_item.quantity),
                    )
                    if result.rowcount != 1:
                        database.rollback()
                        return Response.warning("Item out of stock.")
            ShoppingCartAPI.clearInTransaction(database, customerID)

        order = Order(order_id, total_amount)
        order.placeOrder()
        cart._completeCheckout(order)
        return Response.ok("Order placed successfully.", order)
