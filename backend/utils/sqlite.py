import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

from backend.utils.logger import get_logger

logger = get_logger(__name__)


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


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
        cursor = self._connection.execute(statement, parameters)
        return ExecutionResult(cursor.lastrowid, cursor.rowcount)

    def fetch_one(
        self, statement: str, parameters: Sequence[object] = ()
    ) -> tuple[object, ...] | None:
        return self._connection.execute(statement, parameters).fetchone()

    def fetch_all(
        self, statement: str, parameters: Sequence[object] = ()
    ) -> list[tuple[object, ...]]:
        return self._connection.execute(statement, parameters).fetchall()

    def rollback(self) -> None:
        self._connection.rollback()

    def executescript(self, script: str) -> None:
        self._connection.executescript(script)


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
    ) -> Iterator[SQLiteSession]:
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
            logger.exception("SQLite session failed for %s", self.database_path)
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

    def execute(
        self, statement: str, parameters: Sequence[object] = ()
    ) -> ExecutionResult:
        with self.session(transaction=True) as session:
            return session.execute(statement, parameters)

    @contextmanager
    def transaction(self, *, immediate: bool = False) -> Iterator[SQLiteSession]:
        with self.session(transaction=True, immediate=immediate) as session:
            yield session
