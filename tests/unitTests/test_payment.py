import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.services.payment import Payment, PaymentGateway


class PaymentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payment = Payment(1, 101, 42.50, "Credit Card")

    def test_payment_starts_unpaid(self) -> None:
        self.assertEqual(self.payment.paymentId, 1)
        self.assertEqual(self.payment.orderId, 101)
        self.assertEqual(self.payment.amount, 42.50)
        self.assertEqual(self.payment.paymentMethod, "Credit Card")
        self.assertIsNone(self.payment.paymentDate)
        self.assertEqual(self.payment.paidStatus, "Pending")
        self.assertEqual(self.payment.details, "")

    def test_valid_card_marks_payment_successful(self) -> None:
        result = self.payment.processPayment(
            "4242424242424242",
            "12/30",
            "123",
        )

        self.assertEqual(result, "Paid")
        self.assertEqual(self.payment.paidStatus, "Paid")
        self.assertEqual(self.payment.details, "Payment Successful")

    def test_declined_test_card_marks_payment_failed(self) -> None:
        result = self.payment.processPayment(
            "4000000000000002",
            "12/30",
            "1234",
        )

        self.assertEqual(result, "Failed")
        self.assertEqual(self.payment.paidStatus, "Failed")
        self.assertEqual(self.payment.details, "Payment Failed")

    def test_malformed_payment_fields_are_declined(self) -> None:
        invalid_inputs = (
            ("", "12/30", "123"),
            ("4242424242424242", "", "123"),
            ("4242424242424242", "12/30", ""),
            ("4111111111111111", "12/30", "123"),
        )
        for card_number, expiration_date, cvv in invalid_inputs:
            with self.subTest(card_number=card_number):
                self.assertFalse(
                    PaymentGateway().validatePayment(
                        card_number,
                        expiration_date,
                        cvv,
                    )
                )


if __name__ == "__main__":
    unittest.main()
