
from datetime import datetime
from decimal import Decimal
class payment:
    paymentId: int
    paymentDate: datetime
    paidStatus: bool
    totalAmount: Decimal
    details: str
