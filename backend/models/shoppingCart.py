from backend.models.cartItem import CartItem
from backend.models.item import Item
from backend.models.order import Order


class ShoppingCart:
    def __init__(self, cartId: int) -> None:
        self.cartId = cartId
        self.items: dict[int, CartItem] = {}

    def addItem(self, item: Item, quantity: int = 1) -> str:
        itemId = item.itemId
        current = self.items[itemId].quantity if itemId in self.items else 0
        if quantity <= 0 or (
            hasattr(item, "stockQuantity")
            and current + quantity > item.checkStock()
        ):
            return "Invalid quantity or out of stock."
        self.items[itemId] = CartItem(item, current + quantity)
        return "Item added."

    def removeItem(self, itemId: int) -> str:
        if itemId not in self.items:
            return "Item not found."
        del self.items[itemId]
        return "Item removed."

    def updateQuantity(self, itemId: int, quantity: int) -> str:
        if itemId not in self.items:
            return "Item not found."
        item = self.items[itemId].item
        if quantity <= 0 or (
            hasattr(item, "stockQuantity") and quantity > item.checkStock()
        ):
            return "Invalid quantity or out of stock."
        self.items[itemId].quantity = quantity
        return "Quantity updated."

    def calculateTotal(self) -> float:
        return sum(cart_item.getSubtotal() for cart_item in self.items.values())

    def checkout(self, orderId: int) -> Order | str:
        if not self.items:
            return "Cart is empty."
        stock_error = self._stockError()
        if stock_error is not None:
            return stock_error
        order = Order(orderId, self.calculateTotal())
        order.placeOrder()
        return self._completeCheckout(order)

    def _stockError(self) -> str | None:
        for cart_item in self.items.values():
            item = cart_item.item
            if (
                hasattr(item, "stockQuantity")
                and cart_item.quantity > item.checkStock()
            ):
                return "Item out of stock."
        return None

    def _completeCheckout(self, order: Order) -> Order:
        for cart_item in self.items.values():
            item = cart_item.item
            if hasattr(item, "stockQuantity"):
                item.stockQuantity -= cart_item.quantity
        self.items.clear()
        return order


shoppingCart = ShoppingCart