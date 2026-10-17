# Connect the database and backend.

from backend.models.user import user as User
from database.db import initialize_database

if __name__ == "__main__":
    initialize_database()

    user1 = User(
        name="Alice",
        email="alice@example.com"
    )

    print("Name:", user1.name)
    print("Email:", user1.email)
    print("User ID:", user1.userID)
