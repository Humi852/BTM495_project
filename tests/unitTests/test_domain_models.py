import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.models.event import Event
from backend.models.appointment import Appointment
from backend.models.inventory import Inventory as ModelInventory
from backend.models.item import Item
from backend.models.order import Order
from backend.models.part import Part
from backend.models.shopping_cart import ShoppingCart
from backend.apis.shopping_cart_api import ShoppingCartAPI
from backend.apis.inventory_api import (
    Inventory,
    Item as ServiceItem,
    Part as ServicePart,
)
from backend.utils.response import Response, ResponseLevel
from database.sqlite_database import initialize_database


class EventTests(unittest.TestCase):
    def setUp(self) -> None:
        self.event = Event(
            1,
            "Bike Clinic",
            "Repair workshop",
            "Main Street",
            datetime(2026, 11, 1),
            12,
        )

    def test_create_update_and_cancel_event(self) -> None:
        events: dict[int, Event] = {}

        self.assertEqual(self.event.status, "Active")
        self.assertEqual(self.event.createEvent(events).msg, "Event created successfully.")
        self.assertIs(events[1], self.event)
        self.assertEqual(self.event.createEvent(events).msg, "Invalid event information.")
        self.assertEqual(
            self.event.updateDetails(location="Community Hall", ignored="value").msg,
            "Event updated successfully.",
        )
        self.assertEqual(self.event.location, "Community Hall")
        self.assertFalse(hasattr(self.event, "ignored"))
        self.assertEqual(self.event.cancel().msg, "Event cancelled successfully.")
        self.assertEqual(self.event.status, "Cancelled")

    def test_rejects_invalid_event(self) -> None:
        event = Event(2, "", "Description", "Location", datetime.now(), 0)

        self.assertEqual(event.createEvent({}).msg, "Invalid event information.")

    def test_updates_event_fields_from_model_metadata(self) -> None:
        response = self.event.updateDetails(
            eventName="Bike Maintenance Clinic",
            eventID=99,
            status="Cancelled",
            unknown="ignored",
        )

        self.assertEqual(response.level, ResponseLevel.SUCCESS)
        self.assertTrue(response.success)
        self.assertEqual(self.event.eventName, "Bike Maintenance Clinic")
        self.assertEqual(self.event.eventID, 1)
        self.assertEqual(self.event.status, "Active")
        self.assertFalse(hasattr(self.event, "unknown"))

    def test_appointment_supports_basic_domain_updates(self) -> None:
        appointment = Appointment(
            1,
            2,
            datetime(2026, 11, 2),
            "Bike tune-up",
        )

        result = appointment.reschedule(datetime(2026, 11, 3))
        self.assertTrue(result.success)
        self.assertEqual(appointment.appointmentTime, datetime(2026, 11, 3))
        self.assertFalse(appointment.reschedule("tomorrow").success)
        self.assertFalse(appointment.updateDescription(" ").success)

    def test_response_has_structured_message_level_success_and_data(self) -> None:
        response = Response.ok("Saved.", data=42)
        warning = Response.warning("Needs attention.")
        error = Response.error("Failed.")

        self.assertEqual(response.msg, "Saved.")
        self.assertEqual(response.level, ResponseLevel.SUCCESS)
        self.assertTrue(response.success)
        self.assertEqual(response.data, 42)
        self.assertEqual(warning.level, ResponseLevel.WARNING)
        self.assertFalse(warning.success)
        self.assertEqual(error.level, ResponseLevel.ERROR)
        self.assertFalse(error.success)

    def test_order_status_update_returns_response(self) -> None:
        order = Order(1, 20.0)

        self.assertTrue(order.updateStatus("Shipped").success)
        self.assertEqual(order.status, "Shipped")
        self.assertFalse(order.updateStatus(" ").success)


class ShoppingCartTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "cart.db"
        initialize_database(self.database_path)
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                "INSERT INTO customer (customer_id, name) VALUES (1, 'Casey')"
            )
            connection.executemany(
                "INSERT INTO item "
                "(item_id, name, description, sellingprice, stock_quantity) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    (10, "Tube", "Inner tube", 8.5, 5),
                    (11, "Tune-up", "Basic service", 30.0, None),
                ],
            )
            connection.commit()
        self.part = Part(10, "Tube", "Inner tube", 8.5, "Tires", "RoadCo", 5)
        self.cart_api = ShoppingCartAPI(self.database_path)
        self.cart = self.cart_api.loadCart(1)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_cart_totals_and_checkout(self) -> None:
        self.assertEqual(self.cart.calculateTotal(), 0)
        self.assertEqual(self.cart_api.addItem(self.cart, self.part, 2).msg, "Item added.")
        self.assertEqual(self.cart_api.addItem(self.cart, self.part, 1).msg, "Item added.")
        self.assertEqual(self.cart.calculateTotal(), 25.5)
        self.assertEqual(
            self.cart_api.updateQuantity(self.cart, 10, 4).msg,
            "Quantity updated.",
        )

        checkout = self.cart.checkout(20)
        order = checkout.data

        self.assertTrue(checkout.success)
        self.assertEqual(order.orderId, 20)
        self.assertEqual(order.status, "Placed")
        self.assertEqual(order.getTotalPrice(), 34.0)
        self.assertEqual(self.part.checkStock(), 1)
        self.assertEqual(self.cart.items, {})
        self.assertEqual(self.cart.calculateTotal(), 0)
        self.assertEqual(self.cart.checkout(21).msg, "Cart is empty.")

    def test_cart_enforces_stock_and_item_presence(self) -> None:
        self.assertEqual(
            self.cart_api.addItem(self.cart, self.part, 6).msg,
            "Invalid quantity or out of stock.",
        )
        self.assertEqual(self.cart_api.removeItem(self.cart, 10).msg, "Item not found.")
        self.assertEqual(self.cart_api.updateQuantity(self.cart, 10, 2).msg, "Item not found.")
        self.assertEqual(self.cart.checkout(20).msg, "Cart is empty.")

        self.assertEqual(
            self.cart_api.addItem(self.cart, Item(99, "Unknown", "", 1.0)).msg,
            "Item not found.",
        )
        self.assertEqual(self.cart.items, {})
        self.assertEqual(
            self.cart_api.addItem(self.cart, self.part, 1.5).msg,
            "Invalid quantity or out of stock.",
        )

        self.cart_api.addItem(self.cart, self.part, 2)
        self.part.stockQuantity = 1
        self.assertEqual(self.cart.checkout(20).msg, "Item out of stock.")
        self.assertEqual(self.part.checkStock(), 1)
        self.assertEqual(self.cart.items[10].quantity, 2)

    def test_non_stock_item_and_removal(self) -> None:
        item = Item(11, "Tune-up", "Basic service", 30.0)

        self.assertEqual(self.cart_api.addItem(self.cart, item, 1).msg, "Item added.")
        self.assertEqual(self.cart_api.removeItem(self.cart, 11).msg, "Item removed.")
        self.assertEqual(self.cart_api.removeItem(self.cart, 11).msg, "Item not found.")

    def test_cart_persists_items_and_reloads_from_database(self) -> None:
        priced_part = Part(10, "Tube", "Inner tube", 7.5, "Tires", "RoadCo", 5)
        self.cart_api.addItem(self.cart, priced_part, 2)
        self.cart_api.addItem(self.cart, priced_part, 1)
        reloaded = self.cart_api.loadCart(1)

        self.assertEqual(reloaded.items[10].quantity, 3)
        self.assertIsInstance(reloaded.items[10].item, Part)
        self.assertEqual(reloaded.calculateTotal(), 22.5)

        self.assertEqual(self.cart_api.updateQuantity(reloaded, 10, 4).msg, "Quantity updated.")
        self.assertEqual(self.cart_api.removeItem(reloaded, 10).msg, "Item removed.")
        self.assertEqual(self.cart_api.loadCart(1).items, {})

    def test_failed_cart_persistence_restores_in_memory_quantity(self) -> None:
        self.cart_api.addItem(self.cart, self.part, 2)
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                "CREATE TRIGGER ignore_cart_updates "
                "BEFORE UPDATE OF items_json ON shopping_cart "
                "BEGIN SELECT RAISE(IGNORE); END"
            )
            connection.commit()

        with self.assertRaisesRegex(RuntimeError, "was not saved"):
            self.cart_api.updateQuantity(self.cart, 10, 4)

        self.assertEqual(self.cart.items[10].quantity, 2)
        self.assertEqual(self.cart_api.loadCart(1).items[10].quantity, 2)


class InventoryTests(unittest.TestCase):
    def test_inventory_api_reexports_domain_models(self) -> None:
        self.assertIs(Inventory, ModelInventory)
        self.assertIs(ServiceItem, Item)
        self.assertIs(ServicePart, Part)

    def test_inventory_add_update_and_stock_queries(self) -> None:
        inventory = Inventory(1)
        part = Part(10, "Tube", "Inner tube", 8.5, "Tires", "RoadCo", 5)

        self.assertEqual(inventory.addItem(part).msg, "Item added successfully.")
        self.assertEqual(inventory.addItem(part).msg, "Item already exists.")
        self.assertEqual(inventory.checkStock(10).data, 5)
        self.assertEqual(inventory.updateItem(10, 3).msg, "Item updated successfully.")
        self.assertEqual(inventory.checkStock(10).data, 3)
        self.assertEqual(inventory.markOutOfStock(10).msg, "Item updated successfully.")
        self.assertEqual(inventory.checkStock(10).data, 0)
        self.assertEqual(inventory.updateItem(10, -1).msg, "Invalid item or quantity.")
        self.assertEqual(inventory.checkStock(99).msg, "Item not found.")


if __name__ == "__main__":
    unittest.main()
