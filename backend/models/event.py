from dataclasses import dataclass, field, fields
from datetime import datetime

from backend.utils.response import Response


@dataclass
class Event:
    eventID: int
    name: str = field(metadata={"updatable": True})
    description: str = field(metadata={"updatable": True})
    location: str = field(metadata={"updatable": True})
    eventDateTime: datetime = field(metadata={"updatable": True})
    participantLimit: int = field(metadata={"updatable": True})
    adminID: int | None = None
    # Matches the 'event' category names in the schema's status table.
    status: str = field(default="Scheduled", init=False)

    def createEvent(self, events: dict[int, "Event"]) -> Response:
        if (
            not self.name
            or not self.eventDateTime
            or self.participantLimit <= 0
            or self.eventID in events
        ):
            return Response.warning("Invalid event information.")
        events[self.eventID] = self
        return Response.ok("Event created successfully.", self)

    def updateDetails(self, **changes: object) -> Response:
        updatable_fields = {
            model_field.name
            for model_field in fields(self)
            if model_field.metadata.get("updatable", False)
        }
        for name, value in changes.items():
            if name in updatable_fields:
                setattr(self, name, value)
        return Response.ok("Event updated successfully.", self)

    def cancel(self) -> Response:
        self.status = "Cancelled"
        return Response.ok("Event cancelled successfully.", self)
