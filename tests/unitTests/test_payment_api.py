import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.apis.payment_api import Payment, PaymentGateway
from backend.models.payment import (
    Payment as ModelPayment,
    PaymentMethod,
    PaymentStatus,
)
from backend.utils.response import ResponseLevel


class PaymentTests(unittest.TestCase):
    def test_payment_api_reexports_domain_model(self) -> None:
        self.assertIs(Payment, ModelPayment)

    def setUp(self) -> None:
        self.payment = Payment(1, 101, 42.50, "Credit Card")

    def test_payment_starts_unpaid(self) -> None:
        self.assertEqual(self.payment.paymentId, 1)
        self.assertEqual(self.payment.orderId, 101)
        self.assertEqual(self.payment.amount, 42.50)
        self.assertEqual(self.payment.paymentMethod, "Credit Card")
        self.assertIsNone(self.payment.paymentDate)
        self.assertEqual(self.payment.paidStatus, PaymentStatus.PENDING)
        self.assertEqual(self.payment.details, "")
        self.assertEqual(PaymentMethod.CREDIT_CARD.value, "Credit Card")
        self.assertEqual(PaymentMethod.CASH.value, "Cash")

    def test_valid_card_marks_payment_successful(self) -> None:
        result = self.payment.processPayment(
            "4242424242424242",
            "12/30",
            "123",
        )

        self.assertTrue(result.success)
        self.assertEqual(result.msg, "Payment Successful")
        self.assertEqual(result.level, ResponseLevel.SUCCESS)
        self.assertEqual(self.payment.paidStatus, PaymentStatus.PAID)
        self.assertEqual(self.payment.details, "Payment Successful")

    def test_declined_test_card_marks_payment_failed(self) -> None:
        result = self.payment.processPayment(
            "4000000000000002",
            "12/30",
            "1234",
        )

        self.assertFalse(result.success)
        self.assertEqual(result.msg, "Payment Failed")
        self.assertEqual(result.level, ResponseLevel.ERROR)
        self.assertEqual(self.payment.paidStatus, PaymentStatus.FAILED)
        self.assertEqual(self.payment.details, "Payment Failed")

    def test_cash_and_invalid_payment_methods_return_structured_responses(self) -> None:
        cash_payment = Payment(2, 102, 25.0, "Cash")
        cash_result = cash_payment.processPayment()

        self.assertTrue(cash_result.success)
        self.assertEqual(cash_result.level, ResponseLevel.LOG)
        self.assertEqual(cash_payment.paidStatus, PaymentStatus.PENDING)
        self.assertTrue(cash_payment.confirmCashPayment().success)
        self.assertEqual(cash_payment.paidStatus, PaymentStatus.PAID)

        invalid_payment = Payment(3, 103, 25.0, "Wire")
        invalid_result = invalid_payment.processPayment()
        self.assertFalse(invalid_result.success)
        self.assertEqual(invalid_result.level, ResponseLevel.ERROR)

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
