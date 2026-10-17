
class user:
    userID: int
    password: str
    name: str
    email: str
    phone: str
    address: str
    isAdmin: bool

    def __init__(self, userID, name, email, password):
        self.userID = userID
        self.name = name
        self.email = email
        self.password = password

    class ManageProfile:

        def validateInformation(self, name, email):
            return bool(name.strip() and "@" in email)

        def validatePassword(self, password, confirmPassword):
            return len(password) >= 8 and password == confirmPassword

        def confirmInformation(self, confirmation):
            return confirmation.lower() == "yes"

        def createAccount(self, name, email, password):
            # Save account to the database
            pass
