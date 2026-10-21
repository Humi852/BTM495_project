from datetime import datetime
from decimal import Decimal


class Order:
    def __init__(self, orderId: int, totalAmount: Decimal | float) -> None:
        self.orderId = orderId
        self.orderDate = datetime.now()
        self.status = "Pending"
        self.totalAmount = totalAmount

    def placeOrder(self) -> str:
        self.status = "Placed"
        return "Order placed successfully."

    def getTotalPrice(self) -> Decimal | float:
        return self.totalAmount

    def updateStatus(self, status: str) -> None:
        self.status = status

order = Order