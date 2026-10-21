from backend.models.user import User


# Admin is a role-specific User with its own database identifier.
class Admin(User):
    def __init__(
        self,
        name: str,
        email: str,
        phone: str = "",
        address: str = "",
        adminID: int | None = None,
        password_hash: str | None = None,
    ) -> None:
        super().__init__(name, email, phone, address, password_hash)
        self.adminID = adminID

    @property
    def isAdmin(self) -> bool:
        return True
