import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import main


class MainTests(unittest.TestCase):
    def test_invalid_payment_method_exits_without_creating_payment(self) -> None:
        with (
            patch("builtins.input", return_value="invalid"),
            patch("main.Payment") as payment_class,
            patch("builtins.print") as print_output,
        ):
            main.main()

        payment_class.assert_not_called()
        print_output.assert_any_call("Invalid payment method.")

    def test_cash_payment_runs_and_displays_result(self) -> None:
        with (
            patch("builtins.input", return_value="2"),
            patch("main.Payment") as payment_class,
            patch("builtins.print") as print_output,
        ):
            payment = payment_class.return_value
            payment.paymentDate = None
            payment.paymentId = 1
            payment.orderId = 101
            payment.amount = 50.0
            payment.paymentMethod = "Cash"
            payment.paidStatus = "Pending"

            main.main()

        payment_class.assert_called_once_with(1, 101, 50.0, "Cash")
        payment.processPayment.assert_called_once_with()
        print_output.assert_any_call("Payment Status:", "Pending")


if __name__ == "__main__":
    unittest.main()
