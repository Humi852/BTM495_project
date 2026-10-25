from datetime import datetime
from pathlib import Path

from backend.apis.shopping_cart_api import ShoppingCartAPI
from backend.models.order import Order
from backend.models.shopping_cart import ShoppingCart
from backend.utils.constants import DatabaseColumns, DatabaseTables, DatabaseValues
from backend.utils.response import Response
from backend.utils.sqlite import SQLComparison, SQLCondition, SQLiteQuery
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
            customer = database.select_one(
                DatabaseTables.CUSTOMER,
                (DatabaseColumns.CUSTOMER_ID,),
                where=(SQLCondition(DatabaseColumns.CUSTOMER_ID, customerID),),
            )
            if customer is None:
                raise ValueError(f"Customer {customerID} does not exist.")
            ShoppingCartAPI.verifyInTransaction(database, cart)

            database_items: dict[int, int | None] = {}
            for cart_item in cart.items.values():
                item_id = cart_item.item.itemId
                row = database.select_one(
                    DatabaseTables.ITEM,
                    (DatabaseColumns.STOCK_QUANTITY,),
                    where=(SQLCondition(DatabaseColumns.ITEM_ID, item_id),),
                )
                if row is None:
                    raise ValueError(f"Item {item_id} does not exist.")
                if row[0] is not None and cart_item.quantity > row[0]:
                    database.rollback()
                    return Response.warning("Item out of stock.")
                database_items[item_id] = row[0]

            result = database.insert(
                DatabaseTables.ORDERS,
                {
                    DatabaseColumns.CUSTOMER_ID: customerID,
                    DatabaseColumns.ORDER_DATE_TIME: datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    DatabaseColumns.TOTAL_AMOUNT: total_amount,
                    DatabaseColumns.STATUS_ID: DatabaseValues.ORDER_STATUS_ID_PENDING,
                },
            )
            order_id = result.lastrowid

            for item_id, cart_item in cart.items.items():
                database.insert(
                    DatabaseTables.ORDER_ITEM,
                    {
                        DatabaseColumns.ORDER_ID: order_id,
                        DatabaseColumns.ITEM_ID: item_id,
                        DatabaseColumns.QUANTITY: cart_item.quantity,
                        DatabaseColumns.UNIT_PRICE: cart_item.item.getPrice(),
                    },
                )
                database_stock = database_items[item_id]
                if database_stock is not None:
                    result = database.update(
                        DatabaseTables.ITEM,
                        {
                            DatabaseColumns.STOCK_QUANTITY: (
                                database_stock - cart_item.quantity
                            )
                        },
                        where=(
                            SQLCondition(DatabaseColumns.ITEM_ID, item_id),
                            SQLCondition(
                                DatabaseColumns.STOCK_QUANTITY,
                                cart_item.quantity,
                                SQLComparison.GREATER_THAN_OR_EQUAL,
                            ),
                        ),
                    )
                    if result.rowcount != 1:
                        database.rollback()
                        return Response.warning("Item out of stock.")
            ShoppingCartAPI.clearInTransaction(database, customerID)

        order = Order(order_id, total_amount)
        order.placeOrder()
        cart._completeCheckout(order)
        return Response.ok("Order placed successfully.", order)
