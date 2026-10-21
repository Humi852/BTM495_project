import sqlite3
from contextlib import closing
from pathlib import Path

DB_PATH = Path(__file__).with_name("lpvr.db") # absolute path to the bike shop database file

# The main function to initialize the SQLite database using the schema.sql file
def initialize_database(database_path: str | Path = DB_PATH) -> None:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        )

if __name__ == "__main__": # run it
    initialize_database()
    print(f"SQLite database initialized: {DB_PATH}")
