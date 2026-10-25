import json
import math
import sqlite3
from datetime import datetime
from pathlib import Path

from backend.models.cart_item import CartItem
from backend.models.item import Item
from backend.models.shopping_cart import ShoppingCart
from backend.utils.constants import DatabaseColumns, DatabaseTables
from backend.utils.response import Response
from backend.utils.sqlite import (
    SQLiteQuery,
    SQLiteSession,
    SQLCondition,
)
from database.sqlite_database import DB_PATH


class ShoppingCartAPI:
    def __init__(self, database_path: str | Path = DB_PATH) -> None:
        self.database = SQLiteQuery(database_path)

    def loadCart(self, customerID: int) -> ShoppingCart:
        cart = ShoppingCart(customerID)
        with self.database.transaction(immediate=True) as database:
            customer = database.select_one(
                DatabaseTables.CUSTOMER,
                (DatabaseColumns.CUSTOMER_ID,),
                where=(
                    SQLCondition(DatabaseColumns.CUSTOMER_ID, customerID),
                ),
            )
            if customer is None:
                raise ValueError(f"Customer {customerID} does not exist.")
            stored_cart = database.select_one(
                DatabaseTables.SHOPPING_CART,
                (DatabaseColumns.ITEMS_JSON,),
                where=(
                    SQLCondition(DatabaseColumns.CUSTOMER_ID, customerID),
                ),
            )
            if stored_cart is None:
                database.insert(
                    DatabaseTables.SHOPPING_CART,
                    {
                        DatabaseColumns.CUSTOMER_ID: customerID,
                        DatabaseColumns.ITEMS_JSON: "[]",
                    },
                )
                return cart
            cart.items = self._deserializeItems(database, stored_cart[0])
        return cart

    def addItem(
        self, cart: ShoppingCart, item: Item, quantity: int = 1
    ) -> Response:
        previous_items = self._copyItems(cart.items)
        result = cart.addItem(item, quantity)
        if not result.success:
            return result
        if self.database.select_one(
            DatabaseTables.ITEM,
            (DatabaseColumns.ITEM_ID,),
            where=(SQLCondition(DatabaseColumns.ITEM_ID, item.itemId),),
        ) is None:
            cart.items = previous_items
            return Response.warning("Item not found.")
        self._saveOrRestore(cart, previous_items)
        return result

    def removeItem(self, cart: ShoppingCart, itemId: int) -> Response:
        previous_items = self._copyItems(cart.items)
        result = cart.removeItem(itemId)
        if not result.success:
            return result
        self._saveOrRestore(cart, previous_items)
        return result

    def updateQuantity(
        self, cart: ShoppingCart, itemId: int, quantity: int
    ) -> Response:
        previous_items = self._copyItems(cart.items)
        result = cart.updateQuantity(itemId, quantity)
        if not result.success:
            return result
        self._saveOrRestore(cart, previous_items)
        return result

    @staticmethod
    def clearInTransaction(database: SQLiteSession, customerID: int) -> None:
        result = database.update(
            DatabaseTables.SHOPPING_CART,
            {
                DatabaseColumns.ITEMS_JSON: "[]",
                DatabaseColumns.UPDATED_AT: datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            },
            where=(SQLCondition(DatabaseColumns.CUSTOMER_ID, customerID),),
        )
        if result.rowcount != 1:
            raise ValueError(
                f"Shopping cart for customer {customerID} does not exist."
            )

    @staticmethod
    def verifyInTransaction(
        database: SQLiteSession, cart: ShoppingCart
    ) -> None:
        stored_cart = database.select_one(
            DatabaseTables.SHOPPING_CART,
            (DatabaseColumns.ITEMS_JSON,),
            where=(
                SQLCondition(DatabaseColumns.CUSTOMER_ID, cart.customerID),
            ),
        )
        if stored_cart is None:
            raise ValueError(
                f"Shopping cart for customer {cart.customerID} does not exist."
            )
        if stored_cart[0] != ShoppingCartAPI.serializeItems(cart):
            raise ValueError("Shopping cart has changed; reload it before checkout.")

    @staticmethod
    def serializeItems(cart: ShoppingCart) -> str:
        return json.dumps(
            [
                {
                    "item_id": item_id,
                    "quantity": cart_item.quantity,
                    "price": cart_item.item.getPrice(),
                }
                for item_id, cart_item in cart.items.items()
            ],
            separators=(",", ":"),
            allow_nan=False,
        )

    def _saveOrRestore(
        self, cart: ShoppingCart, previous_items: dict[int, CartItem]
    ) -> None:
        try:
            self._saveCart(cart)
        except (sqlite3.Error, RuntimeError, ValueError):
            cart.items = previous_items
            raise

    @staticmethod
    def _copyItems(items: dict[int, CartItem]) -> dict[int, CartItem]:
        return {
            item_id: CartItem(cart_item.item, cart_item.quantity)
            for item_id, cart_item in items.items()
        }

    def _saveCart(self, cart: ShoppingCart) -> None:
        items_json = self.serializeItems(cart)
        with self.database.transaction(immediate=True) as database:
            for item_id in cart.items:
                if database.select_one(
                    DatabaseTables.ITEM,
                    (DatabaseColumns.ITEM_ID,),
                    where=(SQLCondition(DatabaseColumns.ITEM_ID, item_id),),
                ) is None:
                    raise ValueError(f"Item {item_id} does not exist.")
            result = database.update(
                DatabaseTables.SHOPPING_CART,
                {
                    DatabaseColumns.ITEMS_JSON: items_json,
                    DatabaseColumns.UPDATED_AT: datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                },
                where=(
                    SQLCondition(DatabaseColumns.CUSTOMER_ID, cart.customerID),
                ),
            )
            if result.rowcount != 1:
                raise RuntimeError(
                    f"Shopping cart for customer {cart.customerID} was not saved."
                )

    @staticmethod
    def _deserializeItems(
        database: SQLiteSession, items_json: str
    ) -> dict[int, CartItem]:
        try:
            stored_items = json.loads(items_json)
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError("Stored shopping cart data is invalid.") from error
        if not isinstance(stored_items, list):
            raise ValueError("Stored shopping cart data must be a list.")

        items: dict[int, CartItem] = {}
        for entry in stored_items:
            if (
                not isinstance(entry, dict)
                or type(entry.get("item_id")) is not int
                or type(entry.get("quantity")) is not int
                or entry["quantity"] <= 0
                or isinstance(entry.get("price"), bool)
                or not isinstance(entry.get("price"), (int, float))
                or not math.isfinite(entry["price"])
            ):
                raise ValueError("Stored shopping cart item is invalid.")
            item_id = entry["item_id"]
            if item_id in items:
                raise ValueError("Stored shopping cart contains duplicate items.")
            row = database.select_one(
                DatabaseTables.ITEM,
                (
                    DatabaseColumns.NAME,
                    DatabaseColumns.DESCRIPTION,
                    DatabaseColumns.CATEGORY,
                    DatabaseColumns.BRAND,
                    DatabaseColumns.STOCK_QUANTITY,
                ),
                where=(SQLCondition(DatabaseColumns.ITEM_ID, item_id),),
            )
            if row is None:
                raise ValueError(f"Item {item_id} in the cart does not exist.")
            name, description, category, brand, stock = row
            item = Item(
                item_id,
                name,
                description or "",
                entry["price"],
                category or "",
                brand or "",
                stock,
            )
            items[item_id] = CartItem(item, entry["quantity"])
        return items
