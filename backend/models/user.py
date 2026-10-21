class User:
    def __init__(
        self,
        name: str,
        email: str,
        phone: str = "",
        address: str = "",
        isAdmin: bool = False,
        userID: int | None = None,
    ) -> None:
        self.userID = userID
        self.name = name
        self.email = email
        self.phone = phone
        self.address = address
        self.isAdmin = isAdmin


user = User
