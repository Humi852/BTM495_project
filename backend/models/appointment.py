from dataclasses import asdict, dataclass
from datetime import datetime
from typing import ClassVar

from backend.utils.constants import StatusID
from backend.utils.response import Response


@dataclass
class Appointment:
    # Updatable fields and their validators; status changes go through cancelAppointment.
    _UPDATABLE: ClassVar[dict[str, object]] = {
        "customerID": lambda value: type(value) is int and value > 0,
        "appointmentTime": lambda value: isinstance(value, datetime),
        "description": lambda value: isinstance(value, str) and bool(value.strip()),
    }

    appointmentID: int
    customerID: int
    appointmentTime: datetime
    description: str
    statusID: StatusID | None = None

    def setupTimeSlot(self, appointmentTime: datetime) -> Response:
        if not isinstance(appointmentTime, datetime):
            return Response.warning("Appointment time must be a datetime.")
        if self.statusID in (StatusID.APPOINTMENT_CANCELLED, StatusID.APPOINTMENT_COMPLETED):
            return Response.warning("Appointment can no longer be changed.")
        self.appointmentTime = appointmentTime
        return Response.ok("Appointment time slot set.", self)

    def createAppointment(self, appointments: dict[int, "Appointment"]) -> Response:
        if (
            not isinstance(self.appointmentTime, datetime)
            or not isinstance(self.description, str)
            or not self.description.strip()
            or self.appointmentID in appointments
        ):
            return Response.warning("Invalid appointment information.")
        self.statusID = StatusID.APPOINTMENT_BOOKED
        appointments[self.appointmentID] = self
        return Response.ok("Appointment created successfully.", self)

    # Test/debug helper only: no production code calls this; it returns a plain dict snapshot.
    def getDetails(self) -> Response:
        return Response.ok("Appointment retrieved.", asdict(self))

    def updateAppointment(self, **changes: object) -> Response:
        """Update any updatable fields at once; only real differences are applied."""
        if self.statusID in (StatusID.APPOINTMENT_CANCELLED, StatusID.APPOINTMENT_COMPLETED):
            return Response.warning("Appointment can no longer be changed.")
        unknown = sorted(set(changes) - set(self._UPDATABLE))
        if unknown:
            return Response.warning(f"Cannot update: {', '.join(unknown)}.")
        invalid = sorted(
            name for name, value in changes.items() if not self._UPDATABLE[name](value)
        )
        if invalid:
            return Response.warning(f"Invalid value for: {', '.join(invalid)}.")

        diff = {
            name: (getattr(self, name), value)
            for name, value in changes.items()
            if getattr(self, name) != value
        }
        if not diff:
            return Response.warning("No changes detected.")
        for name, (_, new_value) in diff.items():
            setattr(self, name, new_value)
        return Response.ok("Appointment updated.", diff)

    def cancelAppointment(self) -> Response:
        if self.statusID != StatusID.APPOINTMENT_BOOKED:
            return Response.warning("Only a booked appointment can be cancelled.")
        self.statusID = StatusID.APPOINTMENT_CANCELLED
        return Response.ok("Appointment cancelled successfully.", self)
