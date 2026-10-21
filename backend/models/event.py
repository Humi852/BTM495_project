from dataclasses import dataclass, field, fields
from datetime import datetime

from backend.utils.response import Response


@dataclass
class Event:
    eventID: int
    eventName: str = field(metadata={"updatable": True})
    description: str = field(metadata={"updatable": True})
    location: str = field(metadata={"updatable": True})
    eventDateTime: datetime = field(metadata={"updatable": True})
    capacity: int = field(metadata={"updatable": True})
    status: str = field(default="Active", init=False)

    def createEvent(self, events: dict[int, "Event"]) -> Response:
        if (
            not self.eventName
            or not self.eventDateTime
            or self.capacity <= 0
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
