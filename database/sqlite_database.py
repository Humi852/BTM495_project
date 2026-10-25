from pathlib import Path

from backend.utils.constants import DatabaseColumns, DatabaseTables
from backend.utils.sqlite import SQLiteQuery, SQLiteSession, quote_identifier

DB_PATH = Path(__file__).with_name("lpvr.db") # absolute path to the bike shop database file

# The main function to initialize the SQLite database using the schema.sql file
def initialize_database(database_path: str | Path = DB_PATH) -> None:
    database = SQLiteQuery(database_path)
    with database.session() as connection:
        connection.executescript(
            Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        )
    with database.transaction() as connection:
        _migrate_item_stock(connection)


def _migrate_item_stock(session: SQLiteSession) -> None:
    # Older databases kept stock on item.stock_quantity; move it into inventory.
    item_table = quote_identifier(DatabaseTables.ITEM)
    columns = [row[1] for row in session.fetch_all(f"PRAGMA table_info({item_table})")]
    if DatabaseColumns.LEGACY_STOCK_QUANTITY not in columns:
        return
    rows = session.select(
        DatabaseTables.ITEM,
        (DatabaseColumns.ITEM_ID, DatabaseColumns.LEGACY_STOCK_QUANTITY),
    )
    for item_id, quantity in rows:
        if quantity is None:
            continue
        session.insert(
            DatabaseTables.INVENTORY,
            {DatabaseColumns.ITEM_ID: item_id, DatabaseColumns.QUANTITY: quantity},
        )
        session.insert(
            DatabaseTables.INVENTORY_HISTORY,
            {
                DatabaseColumns.ITEM_ID: item_id,
                DatabaseColumns.OLD_QUANTITY: None,
                DatabaseColumns.NEW_QUANTITY: quantity,
                DatabaseColumns.REASON: "Migrated from item.stock_quantity",
            },
        )
    session.execute(
        f"ALTER TABLE {item_table} "
        f"DROP COLUMN {quote_identifier(DatabaseColumns.LEGACY_STOCK_QUANTITY)}"
    )

if __name__ == "__main__": # run it
    initialize_database()
    print(f"SQLite database initialized: {DB_PATH}")
