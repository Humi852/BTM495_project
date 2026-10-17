from datetime import datetime

# 1. Payment Class
class Payment:

    def __init__(self, paymentId, orderId, amount, paymentMethod):
        self.paymentId = paymentId
        self.orderId = orderId
        self.paymentDate = None
        self.amount = amount
        self.paymentMethod = paymentMethod
        #paymentMethod can be "Credit Card" or "Cash"
        self.paidStatus = "Pending"
        #Paid Status can be "Pending", "Paid", or "Failed"
        self.details = ""

    # Process Credit Card or Cash Payment
    def processPayment(self, cardNumber="", expirationDate="", cvv=""):

        if self.paymentMethod == "Credit Card":
            gateway = PaymentGateway()

            result = gateway.validatePayment(cardNumber, expirationDate, cvv)

            if result:
                self.paidStatus = "Paid"
                self.paymentDate = datetime.now()
                self.details = "Payment Successful"
            else:
                self.paidStatus = "Failed"
                self.details = "Payment Failed"

        elif self.paymentMethod == "Cash":
            self.paidStatus = "Pending"
            self.details = "Payment to be made at shop"

        else:
            self.paidStatus = "Failed"
            self.details = "Invalid Payment Method"

        print(self.details)
        return self.paidStatus

    # Staff confirms Cash Payment
    def confirmCashPayment(self):

        if self.paymentMethod == "Cash" and self.paidStatus == "Pending":
            self.paidStatus = "Paid"
            self.paymentDate = datetime.now()
            self.details = "Cash Payment Confirmed"
        else:
            self.details = "Cash Payment Confirmation Failed"

        print(self.details)

        return self.paidStatus

# 2. Payment Gateway Class
class PaymentGateway:

    def __init__(self):
        self.gatewayName = "Mock Bank Gateway"

    # Validate Credit Card Information
    def validatePayment(self, cardNumber, expirationDate, cvv):
        # Credit Card must have 16 digits
        if len(cardNumber) != 16 or not cardNumber.isdigit():
            return False
        ## Expiration Date must be in MM/YY format
        if len(expirationDate) != 5 or expirationDate[2] != "/":
            return False

        if not expirationDate[:2].isdigit() or not expirationDate[3:].isdigit():
            return False

        if not 1 <= int(expirationDate[:2]) <= 12:
            return False
        # CVV must have 3 digits
        if len(cvv) != 3 or not cvv.isdigit():
            return False

        # Mock Credit Card number for successful payment
        if cardNumber == "4242424242424242":
            return True

        # Mock Bank Rejection
        return False
