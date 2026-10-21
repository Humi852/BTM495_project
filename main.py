# Connect the database and backend.

from backend.models.user import User
from backend.services.payment import Payment
from database.db import initialize_database

if __name__ == "__main__":
    initialize_database()

    user1 = User(
        name="Alice",
        email="alice@example.com"
    )

    print("Name:", user1.name)
    print("Email:", user1.email)
    print("User ID:", user1.userID if user1.userID is not None else "Not saved")

if __name__ == "__main__":

    print("===== Payment System =====")
    print("1. Credit Card")
    print("2. Cash (Pay at Shop)")

    choice = input("Select payment method (1 or 2): ")

    if choice == "1":
        paymentMethod = "Credit Card"

    elif choice == "2":
        paymentMethod = "Cash"

    else:
        print("Invalid payment method.")
        exit()

    # Create Payment Object
    payment = Payment(1, 101, 50.00, paymentMethod)

    # Credit Card Payment
    if paymentMethod == "Credit Card":

        cardNumber = input("Enter card number (16 digits): ")

        if len(cardNumber) != 16 or not cardNumber.isdigit():
            print("Invalid Card Number. Must contain 16 digits.")
            payment.paidStatus = "Failed"

        else:
            expirationDate = input("Enter expiration date (MM/YY): ")

            if (
                len(expirationDate) != 5
                or expirationDate[2] != "/"
                or not expirationDate[:2].isdigit()
                or not expirationDate[3:].isdigit()
                or not 1 <= int(expirationDate[:2]) <= 12
            ):
                print("Invalid Expiration Date. Use MM/YY.")
                payment.paidStatus = "Failed"

            else:
                cvv = input("Enter CVV (3 digits): ")

                if len(cvv) != 3 or not cvv.isdigit():
                    print("Invalid CVV. Must contain 3 digits.")
                    payment.paidStatus = "Failed"

                else:
                    payment.processPayment(
                        cardNumber,
                        expirationDate,
                        cvv
                    )

    # Cash Payment
    elif paymentMethod == "Cash":
        payment.processPayment()

    # Display Payment Information
    print("\n===== Payment Details =====")
    print("Payment ID:", payment.paymentId)
    print("Order ID:", payment.orderId)
    print(f"Amount: CAD ${payment.amount:.2f}")
    print("Payment Method:", payment.paymentMethod)
    print("Payment Status:", payment.paidStatus)

    if payment.paymentDate:
        print("Payment Date:", payment.paymentDate)
