import re
import sqlite3
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Generator, Mapping, Sequence

from backend.utils.logger import get_logger

logger = get_logger(__name__)


def _format_sql(statement: str) -> str:
    clause_pattern = re.compile(
        r"\s+(FROM|WHERE|ORDER BY|LIMIT|VALUES|SET|AND|OR)\s+",
        re.IGNORECASE,
    )
    return clause_pattern.sub(
        lambda match: f"\n  {match.group(1).upper()} ",
        statement.strip(),
    )


_SQL_MODULE_FILE = Path(__file__).resolve()


def _find_caller() -> str:
    """Return the first caller outside this module as 'Class.method (module)'."""
    frame = sys._getframe(1)
    while frame is not None:
        if Path(frame.f_code.co_filename).resolve() != _SQL_MODULE_FILE:
            code = frame.f_code
            name = getattr(code, "co_qualname", code.co_name)
            return name
        frame = frame.f_back
    return "unknown"


def _log_sql(
    statement: str, parameters: Sequence[object], outcome: str
) -> None:
    suffix = f" [{len(parameters)} param(s) redacted]" if parameters else ""
    logger.debug(
        "%s: %s%s | %s",
        _find_caller(),
        " ".join(statement.split()),
        suffix,
        outcome,
    )


def quote_identifier(identifier: str) -> str:
    if not isinstance(identifier, str) or not identifier or "\x00" in identifier:
        raise ValueError("SQL identifiers must be non-empty strings without NUL.")
    return '"' + identifier.replace('"', '""') + '"'


class SQLComparison(Enum):
    EQUAL = "="
    NOT_EQUAL = "!="
    GREATER_THAN = ">"
    GREATER_THAN_OR_EQUAL = ">="
    LESS_THAN = "<"
    LESS_THAN_OR_EQUAL = "<="
    LIKE = "LIKE"
    NOT_LIKE = "NOT LIKE"
    IN = "IN"
    NOT_IN = "NOT IN"


class SQLSortDirection(Enum):
    ASCENDING = "ASC"
    DESCENDING = "DESC"


class SQLDataType(Enum):
    INTEGER = "INTEGER"
    REAL = "REAL"
    TEXT = "TEXT"
    BLOB = "BLOB"
    NUMERIC = "NUMERIC"


@dataclass(frozen=True)
class SQLCondition:
    column: str
    value: object
    comparison: SQLComparison = SQLComparison.EQUAL


@dataclass(frozen=True)
class SQLOrder:
    column: str
    direction: SQLSortDirection = SQLSortDirection.ASCENDING


@dataclass(frozen=True)
class SQLColumnDefinition:
    name: str
    data_type: SQLDataType
    primary_key: bool = False
    not_null: bool = False
    unique: bool = False


class SQLBuilder:
    @staticmethod
    def select(
        table: str,
        columns: Sequence[str] = ("*",),
        *,
        where: Sequence[SQLCondition] = (),
        order_by: Sequence[SQLOrder] = (),
        limit: int | None = None,
    ) -> tuple[str, tuple[object, ...]]:
        if not columns:
            raise ValueError("SELECT requires at least one column.")
        statement = (
            "SELECT "
            + ", ".join(
                "*" if column == "*" else quote_identifier(column)
                for column in columns
            )
            + f" FROM {quote_identifier(table)}"
        )
        parameters: list[object] = []
        if where:
            predicates = [
                SQLBuilder._condition(condition, parameters)
                for condition in where
            ]
            statement += " WHERE " + " AND ".join(predicates)
        if order_by:
            statement += " ORDER BY " + ", ".join(
                f"{quote_identifier(order.column)} {order.direction.value}"
                for order in order_by
            )
        if limit is not None:
            if type(limit) is not int or limit < 0:
                raise ValueError("SELECT limit must be a non-negative integer.")
            statement += " LIMIT ?"
            parameters.append(limit)
        return statement, tuple(parameters)

    @staticmethod
    def insert(table: str, values: Mapping[str, object]) -> tuple[str, tuple[object, ...]]:
        if not values:
            raise ValueError("INSERT requires at least one value.")
        columns = tuple(values)
        statement = (
            f"INSERT INTO {quote_identifier(table)} "
            f"({', '.join(quote_identifier(column) for column in columns)}) "
            f"VALUES ({', '.join('?' for _ in columns)})"
        )
        return statement, tuple(values[column] for column in columns)

    @staticmethod
    def update(
        table: str,
        values: Mapping[str, object],
        *,
        where: Sequence[SQLCondition],
    ) -> tuple[str, tuple[object, ...]]:
        if not values:
            raise ValueError("UPDATE requires at least one value.")
        if not where:
            raise ValueError("UPDATE requires at least one condition.")
        parameters: list[object] = list(values.values())
        assignments = ", ".join(
            f"{quote_identifier(column)} = ?" for column in values
        )
        predicates = [
            SQLBuilder._condition(condition, parameters)
            for condition in where
        ]
        statement = (
            f"UPDATE {quote_identifier(table)} SET {assignments} "
            f"WHERE {' AND '.join(predicates)}"
        )
        return statement, tuple(parameters)

    @staticmethod
    def delete(
        table: str,
        *,
        where: Sequence[SQLCondition],
    ) -> tuple[str, tuple[object, ...]]:
        if not where:
            raise ValueError("DELETE requires at least one condition.")
        parameters: list[object] = []
        predicates = [
            SQLBuilder._condition(condition, parameters)
            for condition in where
        ]
        return (
            f"DELETE FROM {quote_identifier(table)} "
            f"WHERE {' AND '.join(predicates)}",
            tuple(parameters),
        )

    @staticmethod
    def create_table(
        table: str,
        columns: Sequence[SQLColumnDefinition],
        *,
        if_not_exists: bool = False,
    ) -> str:
        if not columns:
            raise ValueError("CREATE TABLE requires at least one column.")
        declarations = []
        primary_keys = [column for column in columns if column.primary_key]
        if len(primary_keys) > 1:
            raise ValueError("Only one primary-key column is supported.")
        for column in columns:
            declaration = (
                f"{quote_identifier(column.name)} {column.data_type.value}"
            )
            if column.primary_key:
                declaration += " PRIMARY KEY"
            if column.not_null:
                declaration += " NOT NULL"
            if column.unique:
                declaration += " UNIQUE"
            declarations.append(declaration)
        exists_clause = " IF NOT EXISTS" if if_not_exists else ""
        return (
            f"CREATE TABLE{exists_clause} {quote_identifier(table)} "
            f"({', '.join(declarations)})"
        )

    @staticmethod
    def _condition(
        condition: SQLCondition, parameters: list[object]
    ) -> str:
        column = quote_identifier(condition.column)
        comparison = condition.comparison
        if condition.value is None:
            if comparison is SQLComparison.EQUAL:
                return f"{column} IS NULL"
            if comparison is SQLComparison.NOT_EQUAL:
                return f"{column} IS NOT NULL"
            raise ValueError("NULL only supports equality comparisons.")
        if comparison in (SQLComparison.IN, SQLComparison.NOT_IN):
            if (
                not isinstance(condition.value, Sequence)
                or isinstance(condition.value, (str, bytes))
            ):
                raise ValueError("IN comparisons require a sequence of values.")
            values = tuple(condition.value)
            if not values:
                return "0" if comparison is SQLComparison.IN else "1"
            parameters.extend(values)
            placeholders = ", ".join("?" for _ in values)
            return f"{column} {comparison.value} ({placeholders})"
        parameters.append(condition.value)
        return f"{column} {comparison.value} ?"


@dataclass(frozen=True)
class ExecutionResult:
    lastrowid: int | None
    rowcount: int


class SQLiteSession:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def execute(
        self, statement: str, parameters: Sequence[object] = ()
    ) -> ExecutionResult:
        try:
            cursor = self._connection.execute(statement, parameters)
        except sqlite3.Error as error:
            _log_sql(statement, parameters, f"failed: {error}")
            raise
        result = ExecutionResult(cursor.lastrowid, cursor.rowcount)
        _log_sql(
            statement,
            parameters,
            f"found {result.rowcount} row(s) affected (last_row_id={result.lastrowid})",
        )
        return result

    def fetch_one(
        self, statement: str, parameters: Sequence[object] = ()
    ) -> tuple[object, ...] | None:
        try:
            result = self._connection.execute(statement, parameters).fetchone()
        except sqlite3.Error as error:
            _log_sql(statement, parameters, f"failed: {error}")
            raise
        _log_sql(
            statement,
            parameters,
            f"found {'1 row' if result is not None else 'no rows'}",
        )
        return result

    def fetch_all(
        self, statement: str, parameters: Sequence[object] = ()
    ) -> list[tuple[object, ...]]:
        try:
            rows = self._connection.execute(statement, parameters).fetchall()
        except sqlite3.Error as error:
            _log_sql(statement, parameters, f"failed: {error}")
            raise
        _log_sql(statement, parameters, f"found {len(rows)} row(s)")
        return rows

    def select(
        self,
        table: str,
        columns: Sequence[str] = ("*",),
        *,
        where: Sequence[SQLCondition] = (),
        order_by: Sequence[SQLOrder] = (),
        limit: int | None = None,
    ) -> list[tuple[object, ...]]:
        statement, parameters = SQLBuilder.select(
            table,
            columns,
            where=where,
            order_by=order_by,
            limit=limit,
        )
        return self.fetch_all(statement, parameters)

    def select_one(
        self,
        table: str,
        columns: Sequence[str] = ("*",),
        *,
        where: Sequence[SQLCondition] = (),
        order_by: Sequence[SQLOrder] = (),
    ) -> tuple[object, ...] | None:
        statement, parameters = SQLBuilder.select(
            table,
            columns,
            where=where,
            order_by=order_by,
            limit=1,
        )
        return self.fetch_one(statement, parameters)

    def insert(self, table: str, values: Mapping[str, object]) -> "ExecutionResult":
        statement, parameters = SQLBuilder.insert(table, values)
        return self.execute(statement, parameters)

    def update(
        self,
        table: str,
        values: Mapping[str, object],
        *,
        where: Sequence[SQLCondition],
    ) -> "ExecutionResult":
        statement, parameters = SQLBuilder.update(table, values, where=where)
        return self.execute(statement, parameters)

    def delete(
        self, table: str, *, where: Sequence[SQLCondition]
    ) -> "ExecutionResult":
        statement, parameters = SQLBuilder.delete(table, where=where)
        return self.execute(statement, parameters)

    def create_table(
        self,
        table: str,
        columns: Sequence[SQLColumnDefinition],
        *,
        if_not_exists: bool = False,
    ) -> None:
        statement = SQLBuilder.create_table(
            table,
            columns,
            if_not_exists=if_not_exists,
        )
        self._connection.execute(statement)
        _log_sql(statement, (), f"created table '{table}'")

    def list_tables(self) -> list[str]:
        statement = (
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
        rows = self.fetch_all(statement)
        return [row[0] for row in rows]

    def count(self, table: str) -> int:
        statement = f"SELECT COUNT(*) FROM {quote_identifier(table)}"
        row = self.fetch_one(statement)
        if row is None or type(row[0]) is not int:
            raise RuntimeError("SQLite COUNT query did not return an integer.")
        return row[0]

    def rollback(self) -> None:
        self._connection.rollback()

    def executescript(self, script: str) -> None:
        self._connection.executescript(script)
        logger.debug(
            "%s: executed script (%d characters)", _find_caller(), len(script)
        )


class SQLiteQuery:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    @contextmanager
    def session(
        self,
        *,
        read_only: bool = False,
        transaction: bool = False,
        immediate: bool = False,
    ) -> Generator[SQLiteSession, None, None]:
        connection: sqlite3.Connection | None = None
        try:
            if read_only:
                database_uri = f"{self.database_path.resolve().as_uri()}?mode=ro"
                connection = sqlite3.connect(database_uri, uri=True)
            else:
                connection = sqlite3.connect(self.database_path)
                connection.execute("PRAGMA foreign_keys = ON")

            if transaction:
                connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            yield SQLiteSession(connection)
            if transaction:
                connection.commit()
        except sqlite3.Error:
            if connection is not None and transaction:
                connection.rollback()
            raise
        except BaseException:
            if connection is not None and transaction:
                connection.rollback()
            raise
        finally:
            if connection is not None:
                connection.close()

    def fetch_one(
        self,
        statement: str,
        parameters: Sequence[object] = (),
        *,
        read_only: bool = False,
    ) -> tuple[object, ...] | None:
        with self.session(read_only=read_only) as session:
            return session.fetch_one(statement, parameters)

    def fetch_all(
        self,
        statement: str,
        parameters: Sequence[object] = (),
        *,
        read_only: bool = False,
    ) -> list[tuple[object, ...]]:
        with self.session(read_only=read_only) as session:
            return session.fetch_all(statement, parameters)

    def select(
        self,
        table: str,
        columns: Sequence[str] = ("*",),
        *,
        where: Sequence[SQLCondition] = (),
        order_by: Sequence[SQLOrder] = (),
        limit: int | None = None,
        read_only: bool = False,
    ) -> list[tuple[object, ...]]:
        with self.session(read_only=read_only) as session:
            return session.select(
                table,
                columns,
                where=where,
                order_by=order_by,
                limit=limit,
            )

    def select_one(
        self,
        table: str,
        columns: Sequence[str] = ("*",),
        *,
        where: Sequence[SQLCondition] = (),
        order_by: Sequence[SQLOrder] = (),
        read_only: bool = False,
    ) -> tuple[object, ...] | None:
        with self.session(read_only=read_only) as session:
            return session.select_one(
                table,
                columns,
                where=where,
                order_by=order_by,
            )

    def insert(self, table: str, values: Mapping[str, object]) -> ExecutionResult:
        with self.session(transaction=True) as session:
            return session.insert(table, values)

    def update(
        self,
        table: str,
        values: Mapping[str, object],
        *,
        where: Sequence[SQLCondition],
    ) -> ExecutionResult:
        with self.session(transaction=True) as session:
            return session.update(table, values, where=where)

    def delete(
        self, table: str, *, where: Sequence[SQLCondition]
    ) -> ExecutionResult:
        with self.session(transaction=True) as session:
            return session.delete(table, where=where)

    def list_tables(self, *, read_only: bool = False) -> list[str]:
        with self.session(read_only=read_only) as session:
            return session.list_tables()

    def count(self, table: str, *, read_only: bool = False) -> int:
        with self.session(read_only=read_only) as session:
            return session.count(table)

    def create_table(
        self,
        table: str,
        columns: Sequence[SQLColumnDefinition],
        *,
        if_not_exists: bool = False,
    ) -> None:
        with self.session(transaction=True) as session:
            session.create_table(
                table,
                columns,
                if_not_exists=if_not_exists,
            )

    def execute(
        self, statement: str, parameters: Sequence[object] = ()
    ) -> ExecutionResult:
        with self.session(transaction=True) as session:
            return session.execute(statement, parameters)

    @contextmanager
    def transaction(
        self, *, immediate: bool = False
    ) -> Generator[SQLiteSession, None, None]:
        with self.session(transaction=True, immediate=immediate) as session:
            yield session
