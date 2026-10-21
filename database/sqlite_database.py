from pathlib import Path

from backend.utils.sqlite import SQLiteQuery

DB_PATH = Path(__file__).with_name("lpvr.db") # absolute path to the bike shop database file

# The main function to initialize the SQLite database using the schema.sql file
def initialize_database(database_path: str | Path = DB_PATH) -> None:
    database = SQLiteQuery(database_path)
    with database.session() as connection:
        connection.executescript(
            Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        )

if __name__ == "__main__": # run it
    initialize_database()
    print(f"SQLite database initialized: {DB_PATH}")
