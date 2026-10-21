from datetime import datetime
from decimal import Decimal

from backend.utils.response import Response


class Order:
    def __init__(self, orderId: int, totalAmount: Decimal | float) -> None:
        self.orderId = orderId
        self.orderDate = datetime.now()
        self.status = "Pending"
        self.totalAmount = totalAmount

    def placeOrder(self) -> Response:
        self.status = "Placed"
        return Response.ok("Order placed successfully.", self)

    def getTotalPrice(self) -> Decimal | float:
        return self.totalAmount

    def updateStatus(self, status: str) -> Response:
        if not isinstance(status, str) or not status.strip():
            return Response.warning("Order status is required.")
        self.status = status
        return Response.ok("Order status updated.", self)