import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.apis.payment_api import Payment


if __name__ == "__main__":
    # Create a test cash payment.
    payment = Payment(1, 101, 50.00, "Cash")

    # Customer selects Pay at Shop.
    payment.processPayment()

    print("Before Admin Confirmation:", payment.paidStatus.value)

    # Admin confirms the cash payment.
    payment.confirmCashPayment()

    print("After Admin Confirmation:", payment.paidStatus.value)
