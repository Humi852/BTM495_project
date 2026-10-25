from pathlib import Path

from backend.utils.constants import DatabaseColumns, DatabaseTables, StatusID
from backend.utils.response import Response
from backend.utils.sqlite import SQLCondition, SQLiteSession, SQLiteQuery
from database.sqlite_database import DB_PATH


class EventRegistrationAPI:
    """Registrations live in the event_registration table, the single source of truth."""

    def __init__(self, database_path: str | Path = DB_PATH) -> None:
        self.database = SQLiteQuery(database_path)

    def register(self, eventID: int, customerID: int) -> Response:
        if type(customerID) is not int or customerID <= 0:
            return Response.warning("A valid customer ID is required.")
        with self.database.transaction(immediate=True) as session:
            event = self._findEvent(session, eventID)
            if event is None:
                return Response.warning("Event not found.")
            participant_limit, status_id = event
            if status_id not in (None, StatusID.EVENT_SCHEDULED):
                return Response.warning("Event is not open for registration.")
            customer = session.select_one(
                DatabaseTables.CUSTOMER,
                (DatabaseColumns.CUSTOMER_ID,),
                where=(SQLCondition(DatabaseColumns.CUSTOMER_ID, customerID),),
            )
            if customer is None:
                return Response.warning("Customer not found.")
            if self._isRegistered(session, eventID, customerID):
                return Response.warning("Customer is already registered.")
            if self._count(session, eventID) >= participant_limit:
                return Response.warning("Event is full.")
            session.insert(
                DatabaseTables.EVENT_REGISTRATION,
                {
                    DatabaseColumns.EVENT_ID: eventID,
                    DatabaseColumns.CUSTOMER_ID: customerID,
                },
            )
        return Response.ok("Registered for event successfully.", customerID)

    def unregister(self, eventID: int, customerID: int) -> Response:
        with self.database.transaction(immediate=True) as session:
            result = session.delete(
                DatabaseTables.EVENT_REGISTRATION,
                where=(
                    SQLCondition(DatabaseColumns.EVENT_ID, eventID),
                    SQLCondition(DatabaseColumns.CUSTOMER_ID, customerID),
                ),
            )
        if result.rowcount != 1:
            return Response.warning("Registration not found.")
        return Response.ok("Registration removed successfully.", customerID)

    def isFull(self, eventID: int) -> Response:
        with self.database.session(read_only=True) as session:
            event = self._findEvent(session, eventID)
            if event is None:
                return Response.warning("Event not found.")
            return Response.ok(
                "Capacity checked.", self._count(session, eventID) >= event[0]
            )

    def listRegistrations(self, eventID: int) -> Response:
        with self.database.session(read_only=True) as session:
            if self._findEvent(session, eventID) is None:
                return Response.warning("Event not found.")
            rows = session.select(
                DatabaseTables.EVENT_REGISTRATION,
                (DatabaseColumns.CUSTOMER_ID,),
                where=(SQLCondition(DatabaseColumns.EVENT_ID, eventID),),
            )
        return Response.ok("Registrations retrieved.", sorted(row[0] for row in rows))

    @staticmethod
    def _findEvent(session: SQLiteSession, eventID: int) -> tuple | None:
        return session.select_one(
            DatabaseTables.EVENT,
            (DatabaseColumns.PARTICIPANT_LIMIT, DatabaseColumns.STATUS_ID),
            where=(SQLCondition(DatabaseColumns.EVENT_ID, eventID),),
        )

    @staticmethod
    def _count(session: SQLiteSession, eventID: int) -> int:
        return len(
            session.select(
                DatabaseTables.EVENT_REGISTRATION,
                (DatabaseColumns.CUSTOMER_ID,),
                where=(SQLCondition(DatabaseColumns.EVENT_ID, eventID),),
            )
        )

    @staticmethod
    def _isRegistered(session: SQLiteSession, eventID: int, customerID: int) -> bool:
        return (
            session.select_one(
                DatabaseTables.EVENT_REGISTRATION,
                (DatabaseColumns.CUSTOMER_ID,),
                where=(
                    SQLCondition(DatabaseColumns.EVENT_ID, eventID),
                    SQLCondition(DatabaseColumns.CUSTOMER_ID, customerID),
                ),
            )
            is not None
        )
