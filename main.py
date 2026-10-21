from backend.apis.payment_api import Payment, PaymentMethod, PaymentStatus
from backend.utils.validators import (
    is_valid_card_number,
    is_valid_cvv,
    is_valid_expiration_date,
)


def main() -> None:
    print("===== Payment System =====")
    print("1. Credit Card")
    print("2. Cash (Pay at Shop)")

    choice = input("Select payment method (1 or 2): ")

    if choice == "1":
        paymentMethod = PaymentMethod.CREDIT_CARD.value

    elif choice == "2":
        paymentMethod = PaymentMethod.CASH.value

    else:
        print("Invalid payment method.")
        return

    # Create Payment Object
    payment = Payment(1, 101, 50.00, paymentMethod)

    # Credit Card Payment
    if paymentMethod == PaymentMethod.CREDIT_CARD:

        cardNumber = input("Enter card number (16 digits): ")

        if not is_valid_card_number(cardNumber):
            print("Invalid Card Number. Must contain 16 digits.")
            payment.paidStatus = PaymentStatus.FAILED

        else:
            expirationDate = input("Enter expiration date (MM/YY): ")

            if (
                not is_valid_expiration_date(expirationDate)
            ):
                print("Invalid Expiration Date. Use MM/YY.")
                payment.paidStatus = PaymentStatus.FAILED

            else:
                cvv = input("Enter CVV (3 digits): ")

                if not is_valid_cvv(cvv):
                    print("Invalid CVV. Must contain 3 digits.")
                    payment.paidStatus = PaymentStatus.FAILED

                else:
                    payment.processPayment(
                        cardNumber,
                        expirationDate,
                        cvv
                    )

    # Cash Payment
    elif paymentMethod == PaymentMethod.CASH:
        payment.processPayment()

    # Display Payment Information
    print("\n===== Payment Details =====")
    print("Payment ID:", payment.paymentId)
    print("Order ID:", payment.orderId)
    print(f"Amount: CAD ${payment.amount:.2f}")
    print("Payment Method:", payment.paymentMethod)
    print("Payment Status:", payment.paidStatus.value)

    if payment.paymentDate:
        print("Payment Date:", payment.paymentDate)


if __name__ == "__main__":
    main()
