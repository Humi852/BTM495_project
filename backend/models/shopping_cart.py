from backend.models.cart_item import CartItem
from backend.models.item import Item
from backend.models.order import Order
from backend.utils.response import Response


class ShoppingCart:
    def __init__(self, customerID: int) -> None:
        self.customerID = customerID
        self.items: dict[int, CartItem] = {}

    def addItem(self, item: Item, quantity: int = 1) -> Response:
        item_id = item.itemId
        current = self.items[item_id].quantity if item_id in self.items else 0
        if type(quantity) is not int or quantity <= 0 or (
            item.stockQuantity is not None
            and current + quantity > item.stockQuantity
        ):
            return Response.warning("Invalid quantity or out of stock.")
        self.items[item_id] = CartItem(item, current + quantity)
        return Response.ok("Item added.", self.items[item_id])

    def removeItem(self, itemId: int) -> Response:
        if itemId not in self.items:
            return Response.warning("Item not found.")
        del self.items[itemId]
        return Response.ok("Item removed.")

    def updateQuantity(self, itemId: int, quantity: int) -> Response:
        if itemId not in self.items:
            return Response.warning("Item not found.")
        item = self.items[itemId].item
        if type(quantity) is not int or quantity <= 0 or (
            item.stockQuantity is not None and quantity > item.stockQuantity
        ):
            return Response.warning("Invalid quantity or out of stock.")
        self.items[itemId].quantity = quantity
        return Response.ok("Quantity updated.", self.items[itemId])

    def calculateTotal(self) -> float:
        return sum(cart_item.getSubtotal() for cart_item in self.items.values())

    def checkout(self, orderId: int) -> Response:
        if not self.items:
            return Response.warning("Cart is empty.")
        stock_error = self._stockError()
        if not stock_error.success:
            return stock_error
        order = Order(orderId, self.calculateTotal())
        order.placeOrder()
        return self._completeCheckout(order)

    def _stockError(self) -> Response:
        for cart_item in self.items.values():
            item = cart_item.item
            if (
                item.stockQuantity is not None
                and cart_item.quantity > item.stockQuantity
            ):
                return Response.warning("Item out of stock.")
        return Response.ok("Stock is available.")

    def _completeCheckout(self, order: Order) -> Response:
        for cart_item in self.items.values():
            item = cart_item.item
            if item.stockQuantity is not None:
                item.stockQuantity -= cart_item.quantity
        self.items.clear()
        return Response.ok("Order placed successfully.", order)
