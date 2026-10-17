from datetime import datetime  # Records when an order is created.


# Represents one product or service and its quantity in the cart.
class CartItem:
    def __init__(self, item, quantity):
        self.item = item
        self.quantity = quantity

    def getSubtotal(self):
        # Price of one item multiplied by the quantity ordered.
        return self.item.getPrice() * self.quantity


# Manages the customer's shopping cart.
class ShoppingCart:
    def __init__(self, cartId):
        self.cartId = cartId
        self.items = {}  # Stores CartItem objects by item ID.

    def addItem(self, item, quantity=1):
        # Get the quantity already in the cart (zero if not added yet).
        current = self.items[item.itemId].quantity if item.itemId in self.items else 0
        # Reject invalid quantities or requests exceeding available stock.
        if quantity <= 0 or (hasattr(item, "stockQuantity") and
                             current + quantity > item.checkStock()):
            return "Invalid quantity or out of stock."
        # Add the item or increase its existing quantity.
        self.items[item.itemId] = CartItem(item, current + quantity)
        return "Item added."

    def removeItem(self, itemId):
        # Remove the chosen item, if present.
        if itemId not in self.items:
            return "Item not found."
        del self.items[itemId]
        return "Item removed."

    def updateQuantity(self, itemId, quantity):
        # Check that the item exists in the cart.
        if itemId not in self.items:
            return "Item not found."
        item = self.items[itemId].item
        # Check the new quantity against the available stock.
        if quantity <= 0 or (hasattr(item, "stockQuantity") and
                             quantity > item.checkStock()):
            return "Invalid quantity or out of stock."
        self.items[itemId].quantity = quantity
        return "Quantity updated."

    def calculateTotal(self):
        # Add together all item subtotals.
        return sum(cartItem.getSubtotal() for cartItem in self.items.values())

    def checkout(self, orderId):
        # Do not allow checkout with an empty cart.
        if not self.items:
            return "Cart is empty."
        # Check stock again in case availability has changed.
        for cartItem in self.items.values():
            item = cartItem.item
            if hasattr(item, "stockQuantity") and cartItem.quantity > item.checkStock():
                return "Item out of stock."
        # Create an order using the cart total, then mark it as placed.
        order = Order(orderId, self.calculateTotal())
        order.placeOrder()
        return order


# Represents an order created during checkout.
class Order:
    def __init__(self, orderId, totalAmount):
        self.orderId = orderId
        self.orderDate = datetime.now()  # Current date and time.
        self.status = "Pending"
        self.totalAmount = totalAmount

    def placeOrder(self):
        # Confirm the order by changing its status.
        self.status = "Placed"
        return "Order placed successfully."

    def getTotalPrice(self):
        # Return the amount calculated at checkout.
        return self.totalAmount

    def updateStatus(self, status):
        # Change the order status when needed.
        self.status = status
