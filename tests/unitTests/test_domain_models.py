import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.models.event import Event
from backend.models.item import Item
from backend.models.part import Part
from backend.models.shoppingCart import ShoppingCart
from backend.services.inventory import Inventory


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
        self.assertEqual(self.event.createEvent(events), "Event created successfully.")
        self.assertIs(events[1], self.event)
        self.assertEqual(self.event.createEvent(events), "Invalid event information.")
        self.assertEqual(
            self.event.updateDetails(location="Community Hall", ignored="value"),
            "Event updated successfully.",
        )
        self.assertEqual(self.event.location, "Community Hall")
        self.assertFalse(hasattr(self.event, "ignored"))
        self.assertEqual(self.event.cancel(), "Event cancelled successfully.")
        self.assertEqual(self.event.status, "Cancelled")

    def test_rejects_invalid_event(self) -> None:
        event = Event(2, "", "Description", "Location", datetime.now(), 0)

        self.assertEqual(event.createEvent({}), "Invalid event information.")


class ShoppingCartTests(unittest.TestCase):
    def setUp(self) -> None:
        self.part = Part(10, "Tube", "Inner tube", 8.5, "Tires", "RoadCo", 5)
        self.cart = ShoppingCart(1)

    def test_cart_totals_and_checkout(self) -> None:
        self.assertEqual(self.cart.calculateTotal(), 0)
        self.assertEqual(self.cart.addItem(self.part, 2), "Item added.")
        self.assertEqual(self.cart.addItem(self.part, 1), "Item added.")
        self.assertEqual(self.cart.calculateTotal(), 25.5)
        self.assertEqual(self.cart.updateQuantity(10, 4), "Quantity updated.")

        order = self.cart.checkout(20)

        self.assertEqual(order.orderId, 20)
        self.assertEqual(order.status, "Placed")
        self.assertEqual(order.getTotalPrice(), 34.0)

    def test_cart_enforces_stock_and_item_presence(self) -> None:
        self.assertEqual(
            self.cart.addItem(self.part, 6),
            "Invalid quantity or out of stock.",
        )
        self.assertEqual(self.cart.removeItem(10), "Item not found.")
        self.assertEqual(self.cart.updateQuantity(10, 2), "Item not found.")
        self.assertEqual(self.cart.checkout(20), "Cart is empty.")

        self.cart.addItem(self.part, 2)
        self.part.stockQuantity = 1
        self.assertEqual(self.cart.checkout(20), "Item out of stock.")

    def test_non_stock_item_and_removal(self) -> None:
        item = Item(11, "Tune-up", "Basic service", 30.0)

        self.assertEqual(self.cart.addItem(item, 1), "Item added.")
        self.assertEqual(self.cart.removeItem(11), "Item removed.")
        self.assertEqual(self.cart.removeItem(11), "Item not found.")


class InventoryTests(unittest.TestCase):
    def test_inventory_add_update_and_stock_queries(self) -> None:
        inventory = Inventory(1)
        part = Part(10, "Tube", "Inner tube", 8.5, "Tires", "RoadCo", 5)

        self.assertEqual(inventory.addItem(part), "Item added successfully.")
        self.assertEqual(inventory.addItem(part), "Item already exists.")
        self.assertEqual(inventory.checkStock(10), 5)
        self.assertEqual(inventory.updateItem(10, 3), "Item updated successfully.")
        self.assertEqual(inventory.checkStock(10), 3)
        self.assertEqual(inventory.markOutOfStock(10), "Item updated successfully.")
        self.assertEqual(inventory.checkStock(10), 0)
        self.assertEqual(inventory.updateItem(10, -1), "Invalid item or quantity.")
        self.assertEqual(inventory.checkStock(99), "Item not found.")


if __name__ == "__main__":
    unittest.main()
