import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("lpvr.db") # absolute path to the bike shop database file

# The main function to initialize the SQLite database using the schema.sql file
def initialize_database():
    with sqlite3.connect(DB_PATH) as connection:
        # Read the sschema.sql file and load it into the database
        connection.executescript(Path(__file__).with_name("schema.sql").read_text())

if __name__ == "__main__": # run it
    initialize_database()
    print(f"SQLite database initialized: {DB_PATH}")
