#subclass of User class, representing a customer in the system
from backend.models.user import User

class Customer(User):
    def __init__(
        self,
        name: str,
        email: str,
        phone: str = "",
        address: str = "",
        customerID: int | None = None,
        password_hash: str | None = None,
    ) -> None:
        super().__init__(name, email, phone, address, password_hash)
        self.customerID = customerID

    @property
    def isAdmin(self) -> bool:
        return False