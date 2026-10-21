from datetime import datetime
from enum import Enum

from backend.utils.response import Response
from backend.utils.validators import (
    is_valid_card_number,
    is_valid_cvv,
    is_valid_expiration_date,
)


class PaymentStatus(str, Enum):
    PENDING = "Pending"
    PAID = "Paid"
    FAILED = "Failed"


class PaymentMethod(str, Enum):
    CREDIT_CARD = "Credit Card"
    CASH = "Cash"


class Payment:
    def __init__(
        self,
        paymentId: int | None,
        orderId: int,
        amount: float,
        paymentMethod: str,
    ) -> None:
        self.paymentId = paymentId
        self.orderId = orderId
        self.paymentDate: datetime | None = None
        self.amount = amount
        self.paymentMethod = paymentMethod
        self.paidStatus = PaymentStatus.PENDING
        self.details = ""

    def processPayment(
        self,
        cardNumber: str = "",
        expirationDate: str = "",
        cvv: str = "",
    ) -> Response:
        if self.paymentMethod == PaymentMethod.CREDIT_CARD:
            approved = PaymentGateway().validatePayment(
                cardNumber,
                expirationDate,
                cvv,
            )
            if approved:
                self.paidStatus = PaymentStatus.PAID
                self.paymentDate = datetime.now()
                self.details = "Payment Successful"
                return Response.ok(self.details, self)
            self.paidStatus = PaymentStatus.FAILED
            self.details = "Payment Failed"
            return Response.error(self.details, self)

        if self.paymentMethod == PaymentMethod.CASH:
            self.paidStatus = PaymentStatus.PENDING
            self.details = "Payment to be made at shop"
            return Response.info(self.details, self)

        self.paidStatus = PaymentStatus.FAILED
        self.details = "Invalid Payment Method"
        return Response.error(self.details, self)

    def confirmCashPayment(self) -> Response:
        if (
            self.paymentMethod == PaymentMethod.CASH
            and self.paidStatus == PaymentStatus.PENDING
        ):
            self.paidStatus = PaymentStatus.PAID
            self.paymentDate = datetime.now()
            self.details = "Cash Payment Confirmed"
            return Response.ok(self.details, self)
        self.details = "Cash Payment Confirmation Failed"
        return Response.warning(self.details, self)


class PaymentGateway:
    gatewayName = "Mock Bank Gateway"
    APPROVED_CARD_NUMBER = "4242424242424242"

    def validatePayment(
        self,
        cardNumber: str,
        expirationDate: str,
        cvv: str,
    ) -> bool:
        if not (
            is_valid_card_number(cardNumber)
            and is_valid_expiration_date(expirationDate)
            and is_valid_cvv(cvv)
        ):
            return False
        return cardNumber == self.APPROVED_CARD_NUMBER
