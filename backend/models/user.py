from abc import ABC, abstractmethod

## User is the parent class for Admin and Customer. It contains the common attributes and methods for both classes.
class User(ABC):
    def __init__(
        self,
        name: str,
        email: str,
        phone: str = "",
        address: str = "",
        password_hash: str | None = None,
    ) -> None:
        self.name = name
        self.email = email
        self.phone = phone
        self.address = address
        self.password_hash = password_hash

    @property
    @abstractmethod
    def isAdmin(self) -> bool:
        raise NotImplementedError

user = User
