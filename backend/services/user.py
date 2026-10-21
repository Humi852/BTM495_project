import sqlite3
from contextlib import closing
from pathlib import Path

from backend.models.user import User
from database.db import DB_PATH


class UserService:
    def __init__(self, database_path: str | Path = DB_PATH) -> None:
        self.databasePath = Path(database_path)

    def createUser(self, user: User) -> User:
        self._validateProfile(user)
        with closing(sqlite3.connect(self.databasePath)) as connection:
            cursor = connection.execute(
                "INSERT INTO user (name, email, phone, address, is_admin) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    user.name,
                    user.email,
                    user.phone,
                    user.address,
                    int(user.isAdmin),
                ),
            )
            connection.commit()
            user.userID = cursor.lastrowid
        return user

    def getUser(self, userID: int) -> User | None:
        with closing(sqlite3.connect(self.databasePath)) as connection:
            row = connection.execute(
                "SELECT user_id, name, email, phone, address, is_admin "
                "FROM user WHERE user_id = ?",
                (userID,),
            ).fetchone()

        if row is None:
            return None

        return User(
            userID=row[0],
            name=row[1],
            email=row[2],
            phone=row[3] or "",
            address=row[4] or "",
            isAdmin=bool(row[5]),
        )

    def updateProfile(self, user: User) -> bool:
        if user.userID is None:
            return False
        self._validateProfile(user)
        with closing(sqlite3.connect(self.databasePath)) as connection:
            cursor = connection.execute(
                "UPDATE user SET name = ?, email = ?, phone = ?, address = ? "
                "WHERE user_id = ?",
                (
                    user.name,
                    user.email,
                    user.phone,
                    user.address,
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
        error = UserService._profileValidationError(user.name, user.email)
        if error is not None:
            raise ValueError(error)

    @staticmethod
    def _profileValidationError(name: str, email: str) -> str | None:
        if not name.strip():
            return "Name is required."
        if not email.strip():
            return "Email is required."
        if "@" not in email:
            return "Email must contain '@'."
        return None
