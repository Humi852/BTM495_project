from user import user
class ManageUserProfile:
    user1 = user(1, "Humaira", "humi@email.com", "Password123")


    def validateInformation(self, name, email):
        return bool(name.strip() and "@" in email)

    def validatePassword(self, password, confirmPassword):
        return len(password) >= 8 and password == confirmPassword

    def confirmInformation(self, confirmation):
        return confirmation.lower() == "yes"

    def createAccount(self, name, email, password):
        # Save account to the database
        pass

