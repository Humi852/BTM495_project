"""Dry-run website routes for inventory and event registration.

These routes only translate HTTP into calls on InventoryList and
EventRegistrationAPI, so the GUI exercises the same code the app uses.
"""

import sqlite3
from pathlib import Path

from backend.apis.event_registration_api import EventRegistrationAPI
from backend.apis.inventory_list_api import InventoryList, Item
from backend.utils.constants import DatabaseColumns, DatabaseTables, StatusID
from backend.utils.response import Response
from backend.utils.sqlite import SQLCondition, SQLiteQuery, SQLOrder

# JSON key -> InventoryList keyword.
_ITEM_KEYS = {
    "name": "name",
    "description": "description",
    "price": "price",
    "category": "category",
    "brand": "brand",
    "stock_quantity": "stockQuantity",
    "admin_id": "adminId",
    "reason": "reason",
}

RouteResult = tuple[int, dict[str, object]]


def _parts(path: str) -> list[str]:
    parts = path.strip("/").split("/")
    return parts[1:] if parts[:1] == ["api"] else [""]


def is_extra_route(path: str) -> bool:
    return _parts(path)[:1] in (["inventory"], ["events"], ["event-registrations"])


def handle_route(
    database_path: str | Path, method: str, path: str, payload: dict | None
) -> RouteResult:
    parts = _parts(path)
    payload = payload or {}
    try:
        if parts[0] == "inventory":
            return _inventory(InventoryList(database_path), method, parts[1:], payload)
        if parts[0] == "events":
            return _events(database_path, method, parts[1:], payload)
        return _registrations(
            EventRegistrationAPI(database_path), method, parts[1:], payload
        )
    except sqlite3.Error:
        return _error(500, "Database error.")


def _id(value: str) -> int | None:
    return int(value) if value.isascii() and value.isdecimal() else None


def _error(status: int, message: str) -> RouteResult:
    return status, {"status": "error", "message": message}


def _result(response: Response, created: bool = False) -> RouteResult:
    if response.success:
        data = response.data
        return (201 if created else 200), {
            "status": "ok",
            "message": response.msg,
            "data": _item_json(data) if isinstance(data, Item) else data,
        }
    status = 404 if "not found" in response.msg.lower() else 400
    return _error(status, response.msg)


def _item_json(item: Item) -> dict[str, object]:
    return {
        "item_id": item.itemId,
        "name": item.name,
        "description": item.description,
        "price": item.price,
        "category": item.category,
        "brand": item.brand,
        "stock_quantity": item.stockQuantity,
    }


def _inventory(
    inventory: InventoryList, method: str, rest: list[str], payload: dict
) -> RouteResult:
    item_id = _id(rest[0]) if rest else None
    if method == "GET" and not rest:
        items = inventory.listItems().data
        return 200, {"status": "ok", "items": [_item_json(i) for i in items]}
    if method == "GET" and len(rest) == 2 and rest[1] == "history" and item_id:
        if not inventory.findItem(item_id).success:
            return _error(404, "Item not found.")
        return 200, {"status": "ok", "history": inventory.listHistory(item_id).data}
    if method == "POST" and not rest:
        unknown = sorted(set(payload) - set(_ITEM_KEYS) - {"item_id"})
        if unknown:
            return _error(400, f"Unknown field: {', '.join(unknown)}.")
        part = Item(
            payload.get("item_id"),
            payload.get("name"),
            payload.get("description", ""),
            payload.get("price"),
            payload.get("category", ""),
            payload.get("brand", ""),
            payload.get("stock_quantity"),
        )
        return _result(
            inventory.addItem(part, payload.get("admin_id"), payload.get("reason")),
            created=True,
        )
    if method == "PATCH" and len(rest) == 1 and item_id:
        unknown = sorted(set(payload) - set(_ITEM_KEYS))
        if unknown:
            return _error(400, f"Unknown field: {', '.join(unknown)}.")
        changes = {_ITEM_KEYS[key]: value for key, value in payload.items()}
        return _result(inventory.updateItem(item_id, **changes))
    if method == "DELETE" and len(rest) == 1 and item_id:
        return _result(inventory.removeItem(item_id))
    return _error(404, "Not found.")


def _events(
    database_path: str | Path, method: str, rest: list[str], payload: dict
) -> RouteResult:
    database = SQLiteQuery(database_path)
    registrations = EventRegistrationAPI(database_path)
    if method == "GET" and not rest:
        with database.session(read_only=True) as session:
            events = session.select(
                DatabaseTables.EVENT,
                (
                    DatabaseColumns.EVENT_ID,
                    DatabaseColumns.NAME,
                    DatabaseColumns.PARTICIPANT_LIMIT,
                ),
                order_by=(SQLOrder(DatabaseColumns.EVENT_ID),),
            )
            customers = session.select(
                DatabaseTables.CUSTOMER,
                (DatabaseColumns.CUSTOMER_ID, DatabaseColumns.NAME),
                order_by=(SQLOrder(DatabaseColumns.CUSTOMER_ID),),
            )
        return 200, {
            "status": "ok",
            "events": [
                {
                    "event_id": event_id,
                    "name": name,
                    "participant_limit": limit,
                    "customer_ids": registrations.listRegistrations(event_id).data,
                }
                for event_id, name, limit in events
            ],
            "customers": [
                {"customer_id": customer_id, "name": name}
                for customer_id, name in customers
            ],
        }
    if method == "POST" and not rest:
        name, limit = payload.get("name"), payload.get("participant_limit")
        if not isinstance(name, str) or not name.strip():
            return _error(400, "Event name is required.")
        if type(limit) is not int or limit < 0:
            return _error(400, "Participant limit must be a whole number.")
        with database.transaction() as session:
            result = session.insert(
                DatabaseTables.EVENT,
                {
                    DatabaseColumns.NAME: name.strip(),
                    DatabaseColumns.PARTICIPANT_LIMIT: limit,
                    DatabaseColumns.STATUS_ID: StatusID.EVENT_SCHEDULED,
                },
            )
        return 201, {"status": "ok", "event_id": result.lastrowid}
    if method == "DELETE" and len(rest) == 1 and _id(rest[0]) is not None:
        with database.transaction() as session:
            result = session.delete(
                DatabaseTables.EVENT,
                where=(SQLCondition(DatabaseColumns.EVENT_ID, _id(rest[0])),),
            )
        if result.rowcount != 1:
            return _error(404, "Event not found.")
        return 200, {"status": "ok"}
    return _error(404, "Not found.")


def _registrations(
    registrations: EventRegistrationAPI, method: str, rest: list[str], payload: dict
) -> RouteResult:
    if method == "POST" and not rest:
        event_id, customer_id = payload.get("event_id"), payload.get("customer_id")
        if type(event_id) is not int or type(customer_id) is not int:
            return _error(400, "event_id and customer_id must be whole numbers.")
        return _result(registrations.register(event_id, customer_id), created=True)
    if method == "DELETE" and len(rest) == 2:
        event_id, customer_id = _id(rest[0]), _id(rest[1])
        if event_id is None or customer_id is None:
            return _error(404, "Not found.")
        return _result(registrations.unregister(event_id, customer_id))
    return _error(404, "Not found.")
