from datetime import datetime
from decimal import Decimal
from enum import Enum

from backend.utils.response import Response


class OrderStatus(str, Enum):
    PENDING = "Pending"
    CANCELLED = "Cancelled"
    COMPLETED = "Completed"


class Order:
    def __init__(self, orderId: int, totalAmount: Decimal | float) -> None:
        self.orderId = orderId
        self.orderDate = datetime.now()
        self.status = OrderStatus.PENDING.value
        self.totalAmount = totalAmount

    def placeOrder(self) -> Response:
        self.status = OrderStatus.PENDING.value
        return Response.ok("Order placed successfully.", self)

    def getTotalPrice(self) -> Decimal | float:
        return self.totalAmount

    def updateStatus(self, status: str) -> Response:
        if not isinstance(status, str) or not status.strip():
            return Response.warning("Order status is required.")
        if status not in {order_status.value for order_status in OrderStatus}:
            return Response.warning("Invalid order status.")
        self.status = status
        return Response.ok("Order status updated.", self)