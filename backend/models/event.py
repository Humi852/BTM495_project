from datetime import datetime


class Event:
    def __init__(
        self,
        eventID: int,
        eventName: str,
        description: str,
        location: str,
        eventDateTime: datetime,
        capacity: int,
    ) -> None:
        self.eventID = eventID
        self.eventName = eventName
        self.description = description
        self.location = location
        self.eventDateTime = eventDateTime
        self.capacity = capacity
        self.status = "Active"

    def createEvent(self, events: dict[int, "Event"]) -> str:
        if (
            not self.eventName
            or not self.eventDateTime
            or self.capacity <= 0
            or self.eventID in events
        ):
            return "Invalid event information."
        events[self.eventID] = self
        return "Event created successfully."

    def updateDetails(self, **changes: object) -> str:
        allowed_fields = (
            "eventName",
            "description",
            "location",
            "eventDateTime",
            "capacity",
        )
        for field, value in changes.items():
            if field in allowed_fields:
                setattr(self, field, value)
        return "Event updated successfully."

    def cancel(self) -> str:
        self.status = "Cancelled"
        return "Event cancelled successfully."