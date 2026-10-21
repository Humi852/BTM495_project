from abc import ABC, abstractmethod


class User(ABC):
    def __init__(
        self,
        name: str,
        email: str,
        phone: str = "",
        address: str = "",
        userID: int | None = None,
    ) -> None:
        self.userID = userID
        self.name = name
        self.email = email
        self.phone = phone
        self.address = address

    @property
    @property
    @abstractmethod
    def isAdmin(self) -> bool:
        raise NotImplementedError


class Admin(User):
    @property
    def isAdmin(self) -> bool:
        return True


class Customer(User):
    @property
    def isAdmin(self) -> bool:
        return False


user = User
