from dataclasses import dataclass
from datetime import datetime

from backend.utils.response import Response


@dataclass
class Appointment:
    appointmentID: int
    customerID: int
    appointmentTime: datetime
    description: str

    def reschedule(self, appointmentTime: datetime) -> Response:
        if not isinstance(appointmentTime, datetime):
            return Response.warning("Appointment time must be a datetime.")
        self.appointmentTime = appointmentTime
        return Response.ok("Appointment rescheduled.", self)

    def updateDescription(self, description: str) -> Response:
        if not isinstance(description, str) or not description.strip():
            return Response.warning("Appointment description is required.")
        self.description = description
        return Response.ok("Appointment updated.", self)
