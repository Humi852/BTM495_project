# Event Management: create, update, and cancel events.
class Event:
    def __init__(self, eventID, eventName, description, location, eventDateTime, capacity):
        # Store the event details and set its initial status.
        self.eventID = eventID
        self.eventName = eventName
        self.description = description
        self.location = location
        self.eventDateTime = eventDateTime
        self.capacity = capacity
        self.status = 'Active'

    def createEvent(self, events):
        # Check required information and prevent duplicate event IDs.
        if not self.eventName or not self.eventDateTime or self.capacity <= 0 or self.eventID in events:
            return 'Invalid event information.'
        # Add the event to the collection.
        events[self.eventID] = self
        return 'Event created successfully.'

    def updateDetails(self, **changes):
        # Update only the event details allowed by the class.
        for field, value in changes.items():
            if field in ('eventName', 'description', 'location', 'eventDateTime', 'capacity'):
                setattr(self, field, value)
        return 'Event updated successfully.'

    def cancel(self):
        # Mark the event as cancelled without deleting it.
        self.status = 'Cancelled'
        return 'Event cancelled successfully.'
