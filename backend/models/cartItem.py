from backend.models.item import Item


class CartItem:
    def __init__(self, item: Item, quantity: int) -> None:
        self.item = item
        self.quantity = quantity

    def getSubtotal(self) -> float:
        return self.item.getPrice() * self.quantity


cartItem = CartItem