import sqlite3
from datetime import datetime
from pathlib import Path

from backend.models.item import Item
from backend.utils.constants import DatabaseColumns, DatabaseTables
from backend.utils.response import Response
from backend.utils.sqlite import SQLCondition, SQLiteQuery, SQLiteSession, SQLOrder
from database.sqlite_database import DB_PATH

__all__ = ["InventoryList", "Item"]


def _is_number(value: object) -> bool:
    return type(value) in (int, float) and value >= 0


def _is_text(value: object) -> bool:
    return isinstance(value, str)


# Item attribute -> (item table column, value validator).
_ITEM_FIELDS = {
    "name": (DatabaseColumns.NAME, lambda v: _is_text(v) and bool(v.strip())),
    "description": (DatabaseColumns.DESCRIPTION, _is_text),
    "price": (DatabaseColumns.PRICE, _is_number),
    "category": (DatabaseColumns.CATEGORY, _is_text),
    "brand": (DatabaseColumns.BRAND, _is_text),
}
# Stock lives in the inventory table; None means the item is not stock-tracked.
_STOCK_FIELD = "stockQuantity"
_AUDIT_FIELDS = ("adminId", "reason")
_ALL_FIELDS = (*_ITEM_FIELDS, _STOCK_FIELD)

_ITEM_COLUMNS = (DatabaseColumns.ITEM_ID, *(column for column, _ in _ITEM_FIELDS.values()))


def _valid_stock(value: object) -> bool:
    return value is None or (type(value) is int and value >= 0)


class InventoryList:
    """Items plus their stock. Stock is the inventory table; every change is audited."""

    def __init__(self, database_path: str | Path = DB_PATH) -> None:
        self.database = SQLiteQuery(database_path)

    def listItems(self) -> Response:
        with self.database.session(read_only=True) as session:
            rows = session.select(
                DatabaseTables.ITEM,
                _ITEM_COLUMNS,
                order_by=(SQLOrder(DatabaseColumns.ITEM_ID),),
            )
            stock = dict(
                session.select(
                    DatabaseTables.INVENTORY,
                    (DatabaseColumns.ITEM_ID, DatabaseColumns.QUANTITY),
                )
            )
        return Response.ok(
            "Items retrieved.",
            [self._toItem((*row, stock.get(row[0]))) for row in rows],
        )

    def findItem(self, itemId: int) -> Response:
        with self.database.session(read_only=True) as session:
            row = self._findRow(session, itemId)
        if row is None:
            return Response.warning("Item not found.")
        return Response.ok("Item found.", self._toItem(row))

    def listHistory(self, itemId: int) -> Response:
        """Return the audit trail of an item's stock, oldest first."""
        with self.database.session(read_only=True) as session:
            rows = session.select(
                DatabaseTables.INVENTORY_HISTORY,
                (
                    DatabaseColumns.OLD_QUANTITY,
                    DatabaseColumns.NEW_QUANTITY,
                    DatabaseColumns.ADMIN_ID,
                    DatabaseColumns.REASON,
                    DatabaseColumns.CREATED_AT,
                ),
                where=(SQLCondition(DatabaseColumns.ITEM_ID, itemId),),
            )
        history = [
            {
                "oldQuantity": old,
                "newQuantity": new,
                "adminId": adminId,
                "reason": reason,
                "createdAt": createdAt,
            }
            for old, new, adminId, reason, createdAt in rows
        ]
        return Response.ok("History retrieved.", history)

    def addItem(
        self, part: Item, adminId: int | None = None, reason: str | None = None
    ) -> Response:
        values = {name: getattr(part, name) for name in _ITEM_FIELDS}
        if (
            type(part.itemId) is not int
            or part.itemId <= 0
            or self._invalid(values)
            or not _valid_stock(part.stockQuantity)
        ):
            return Response.warning("Invalid item information.")
        try:
            with self.database.transaction(immediate=True) as session:
                if self._findRow(session, part.itemId) is not None:
                    return Response.warning("Item already exists.")
                session.insert(
                    DatabaseTables.ITEM,
                    {
                        DatabaseColumns.ITEM_ID: part.itemId,
                        **{
                            _ITEM_FIELDS[name][0]: value
                            for name, value in values.items()
                        },
                    },
                )
                self.setQuantityInTransaction(
                    session, part.itemId, part.stockQuantity, adminId, reason or "Item added"
                )
        except sqlite3.IntegrityError:
            return Response.warning("Invalid item information.")
        return Response.ok("Item added successfully.", part)

    def updateItem(self, itemId: int, **changes: object) -> Response:
        """Update any item or stock fields at once; only real differences are written.

        `adminId` and `reason` are not item fields: they are recorded in the
        inventory history when stockQuantity changes.
        """
        adminId = changes.pop("adminId", None)
        reason = changes.pop("reason", None)
        unknown = sorted(set(changes) - set(_ALL_FIELDS))
        if unknown:
            return Response.warning(f"Cannot update: {', '.join(unknown)}.")
        invalid = self._invalid(
            {name: value for name, value in changes.items() if name in _ITEM_FIELDS}
        )
        if _STOCK_FIELD in changes and not _valid_stock(changes[_STOCK_FIELD]):
            invalid.append(_STOCK_FIELD)
        if invalid:
            return Response.warning(f"Invalid value for: {', '.join(sorted(invalid))}.")
        try:
            with self.database.transaction(immediate=True) as session:
                row = self._findRow(session, itemId)
                if row is None:
                    return Response.warning("Item not found.")
                current = self._toItem(row)
                diff = {
                    name: (getattr(current, name), value)
                    for name, value in changes.items()
                    if getattr(current, name) != value
                }
                if not diff:
                    return Response.warning("No changes detected.")
                item_changes = {
                    _ITEM_FIELDS[name][0]: new
                    for name, (_, new) in diff.items()
                    if name in _ITEM_FIELDS
                }
                if item_changes:
                    session.update(
                        DatabaseTables.ITEM,
                        item_changes,
                        where=(SQLCondition(DatabaseColumns.ITEM_ID, itemId),),
                    )
                if _STOCK_FIELD in diff:
                    self.setQuantityInTransaction(
                        session, itemId, diff[_STOCK_FIELD][1], adminId, reason
                    )
        except sqlite3.IntegrityError:
            return Response.warning("Unknown admin.")
        return Response.ok("Item updated successfully.", diff)

    def removeItem(self, itemId: int) -> Response:
        try:
            with self.database.transaction(immediate=True) as session:
                row = self._findRow(session, itemId)
                if row is None:
                    return Response.warning("Item not found.")
                session.delete(
                    DatabaseTables.ITEM,
                    where=(SQLCondition(DatabaseColumns.ITEM_ID, itemId),),
                )
        except sqlite3.IntegrityError:
            return Response.warning("Item is used by existing orders.")
        return Response.ok("Item removed successfully.", self._toItem(row))

    @staticmethod
    def setQuantityInTransaction(
        session: SQLiteSession,
        itemId: int,
        quantity: int | None,
        adminId: int | None = None,
        reason: str | None = None,
    ) -> bool:
        """Set an item's stock and append a history row. Returns False if unchanged.

        Must run inside the caller's transaction so the stock change and its
        history row commit (or roll back) together.
        """
        where = (SQLCondition(DatabaseColumns.ITEM_ID, itemId),)
        row = session.select_one(
            DatabaseTables.INVENTORY, (DatabaseColumns.QUANTITY,), where=where
        )
        old = None if row is None else row[0]
        if old == quantity:
            return False
        if quantity is None:
            session.delete(DatabaseTables.INVENTORY, where=where)
        elif old is None:
            session.insert(
                DatabaseTables.INVENTORY,
                {
                    DatabaseColumns.ITEM_ID: itemId,
                    DatabaseColumns.QUANTITY: quantity,
                    DatabaseColumns.ADMIN_ID: adminId,
                },
            )
        else:
            result = session.update(
                DatabaseTables.INVENTORY,
                {
                    DatabaseColumns.QUANTITY: quantity,
                    DatabaseColumns.ADMIN_ID: adminId,
                    DatabaseColumns.UPDATED_AT: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                },
                where=where,
            )
            if result.rowcount != 1:
                return False
        session.insert(
            DatabaseTables.INVENTORY_HISTORY,
            {
                DatabaseColumns.ITEM_ID: itemId,
                DatabaseColumns.OLD_QUANTITY: old,
                DatabaseColumns.NEW_QUANTITY: quantity,
                DatabaseColumns.ADMIN_ID: adminId,
                DatabaseColumns.REASON: reason,
            },
        )
        return True

    @staticmethod
    def _invalid(values: dict[str, object]) -> list[str]:
        return sorted(
            name for name, value in values.items() if not _ITEM_FIELDS[name][1](value)
        )

    @staticmethod
    def stockOf(session: SQLiteSession, itemId: int) -> int | None:
        """Return an item's tracked quantity, or None when it is not stock-tracked."""
        row = session.select_one(
            DatabaseTables.INVENTORY,
            (DatabaseColumns.QUANTITY,),
            where=(SQLCondition(DatabaseColumns.ITEM_ID, itemId),),
        )
        return None if row is None else row[0]

    @staticmethod
    def _findRow(session: SQLiteSession, itemId: int) -> tuple | None:
        row = session.select_one(
            DatabaseTables.ITEM,
            _ITEM_COLUMNS,
            where=(SQLCondition(DatabaseColumns.ITEM_ID, itemId),),
        )
        if row is None:
            return None
        return (*row, InventoryList.stockOf(session, itemId))

    @staticmethod
    def _toItem(row: tuple) -> Item:
        itemId, name, description, price, category, brand, stock = row
        return Item(
            itemId, name, description or "", price, category or "", brand or "", stock
        )
