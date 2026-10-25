from pathlib import Path

from backend.utils.constants import (
    DATABASE_SCHEMA_COLUMNS,
    DatabaseColumns,
    DatabaseTables,
    StatusID,
)
from backend.utils.sqlite import SQLiteQuery, SQLiteSession, quote_identifier

DB_PATH = Path(__file__).with_name("lpvr.db") # absolute path to the bike shop database file

_LEGACY_SUFFIX = "_legacy"
# Tables that carried the old category-scoped status foreign key, children first.
_STATUS_TABLES = (
    DatabaseTables.PAYMENT,
    DatabaseTables.ORDERS,
    DatabaseTables.APPOINTMENT,
    DatabaseTables.EVENT,
)
# Old category-scoped status IDs (event 1-3, appointment 4-6, order 7-9, payment 10-12)
# mapped onto the three generic statuses.
_LEGACY_STATUS_IDS = {
    1: StatusID.PENDING, 2: StatusID.COMPLETED, 3: StatusID.CANCELLED,
    4: StatusID.PENDING, 5: StatusID.CANCELLED, 6: StatusID.COMPLETED,
    7: StatusID.PENDING, 8: StatusID.CANCELLED, 9: StatusID.COMPLETED,
    10: StatusID.PENDING, 11: StatusID.COMPLETED, 12: StatusID.CANCELLED,
}


# The main function to initialize the SQLite database using the schema.sql file
def initialize_database(database_path: str | Path = DB_PATH) -> None:
    database = SQLiteQuery(database_path)
    _park_legacy_status_tables(database)
    with database.session() as connection:
        connection.executescript(
            Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        )
    with database.transaction() as connection:
        _restore_legacy_status_rows(connection)
        _migrate_item_stock(connection)


def _table_names(session: SQLiteSession) -> set[str]:
    return {
        row[0]
        for row in session.fetch_all("SELECT name FROM sqlite_master WHERE type = 'table'")
    }


def _park_legacy_status_tables(database: SQLiteQuery) -> None:
    """Move rows built on the old category-scoped status table into plain *_legacy tables.

    The old tables cannot be kept around: their foreign keys point at a status key that
    no longer exists, which makes SQLite reject any write to the new status table.
    """
    with database.session() as session:
        tables = _table_names(session)
        status_table = quote_identifier(DatabaseTables.STATUS)
        status_columns = [
            row[1] for row in session.fetch_all(f"PRAGMA table_info({status_table})")
        ]
        old_status_table = DatabaseColumns.CATEGORY in status_columns
        stale_parked = [
            table
            for table in _STATUS_TABLES
            if table + _LEGACY_SUFFIX in tables and _has_foreign_keys(session, table + _LEGACY_SUFFIX)
        ]
        if not old_status_table and not stale_parked and DatabaseTables.STATUS + _LEGACY_SUFFIX not in tables:
            return
        session.execute("PRAGMA foreign_keys = OFF")
        session.execute("BEGIN")
        try:
            if old_status_table:
                for table in _STATUS_TABLES:
                    legacy = quote_identifier(table + _LEGACY_SUFFIX)
                    if table + _LEGACY_SUFFIX not in tables:
                        session.execute(
                            f"CREATE TABLE {legacy} AS SELECT * FROM {quote_identifier(table)}"
                        )
                    session.execute(f"DROP TABLE {quote_identifier(table)}")
                session.execute(f"DROP TABLE {status_table}")
            for table in stale_parked:
                legacy = quote_identifier(table + _LEGACY_SUFFIX)
                flat = quote_identifier(table + "_flat")
                session.execute(f"CREATE TABLE {flat} AS SELECT * FROM {legacy}")
                session.execute(f"DROP TABLE {legacy}")
                session.execute(f"ALTER TABLE {flat} RENAME TO {legacy}")
            session.execute(
                f"DROP TABLE IF EXISTS {quote_identifier(DatabaseTables.STATUS + _LEGACY_SUFFIX)}"
            )
            session.execute("COMMIT")
        except BaseException:
            session.rollback()
            raise


def _has_foreign_keys(session: SQLiteSession, table: str) -> bool:
    return bool(session.fetch_all(f"PRAGMA foreign_key_list({quote_identifier(table)})"))


def _restore_legacy_status_rows(session: SQLiteSession) -> None:
    """Copy rows from parked tables into the new ones, mapping old status IDs."""
    parked = _table_names(session)
    for table in reversed(_STATUS_TABLES):  # parents before children
        legacy_table = table + _LEGACY_SUFFIX
        if legacy_table not in parked:
            continue
        columns = DATABASE_SCHEMA_COLUMNS[table]
        for row in session.select(legacy_table, columns):
            values = dict(zip(columns, row))
            status_id = values[DatabaseColumns.STATUS_ID]
            if status_id is not None:
                values[DatabaseColumns.STATUS_ID] = int(_LEGACY_STATUS_IDS[status_id])
            session.insert(table, values)
        session.execute(f"DROP TABLE {quote_identifier(legacy_table)}")

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
