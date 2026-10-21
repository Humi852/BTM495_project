import sqlite3
from contextlib import closing
from pathlib import Path

from backend.models.user import Admin, Customer, User
from database.db import DB_PATH


class UserService:
    def __init__(self, database_path: str | Path = DB_PATH) -> None:
        self.databasePath = Path(database_path)

    def createUser(self, user: User) -> User:
        self._validateProfile(user)
        role_table, _ = self._roleTable(user)
        with closing(sqlite3.connect(self.databasePath)) as connection:
            cursor = connection.execute(
                f"INSERT INTO {role_table} "
                "(name, email, phone, address, password_hash) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    user.name,
                    user.email,
                    user.phone,
                    user.address,
                    user.password_hash,
                ),
            )
            connection.commit()
            user.userID = cursor.lastrowid
        return user

    def getUser(self, userID: int, userType: type[User]) -> User | None:
        role_table, id_column = self._roleTableForType(userType)
        with closing(sqlite3.connect(self.databasePath)) as connection:
            row = connection.execute(
                f"SELECT {id_column}, name, email, phone, address, password_hash "
                f"FROM {role_table} WHERE {id_column} = ?",
                (userID,),
            ).fetchone()

        if row is None:
            return None

        return userType(
            userID=row[0],
            name=row[1],
            email=row[2],
            phone=row[3] or "",
            address=row[4] or "",
            password_hash=row[5],
        )

    def updateProfile(self, user: User) -> bool:
        if user.userID is None:
            return False
        self._validateProfile(user)
        role_table, id_column = self._roleTable(user)
        with closing(sqlite3.connect(self.databasePath)) as connection:
            cursor = connection.execute(
                f"UPDATE {role_table} SET name = ?, email = ?, phone = ?, "
                f"address = ?, password_hash = ? WHERE {id_column} = ?",
                (
                    user.name,
                    user.email,
                    user.phone,
                    user.address,
                    user.password_hash,
                    user.userID,
                ),
            )
            connection.commit()
        return cursor.rowcount > 0

    @staticmethod
    def validateInformation(name: str, email: str) -> bool:
        return UserService._profileValidationError(name, email) is None

    @staticmethod
    def confirmInformation(confirmation: str) -> bool:
        return confirmation.lower() == "yes"

    @staticmethod
    def _validateProfile(user: User) -> None:
        UserService._roleTable(user)
        error = UserService._profileValidationError(user.name, user.email)
        if error is not None:
            raise ValueError(error)

    @staticmethod
    def _roleTable(user: User) -> tuple[str, str]:
        return UserService._roleTableForType(type(user))

    @staticmethod
    def _roleTableForType(userType: type[User]) -> tuple[str, str]:
        if userType is Admin:
            return "admin", "admin_id"
        if userType is Customer:
            return "customer", "customer_id"
        raise TypeError("Profiles must be an Admin or Customer.")

    @staticmethod
    def _profileValidationError(name: str, email: str) -> str | None:
        if not name.strip():
            return "Name is required."
        if not email.strip():
            return "Email is required."
        if "@" not in email:
            return "Email must contain '@'."
        return None
