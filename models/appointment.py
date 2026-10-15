class Appointment:
    def __init__(self, id, bicycle, issueDescription, bookedSlot, statusID):
        self.id = id
        self.bicycle = bicycle
        self.issueDescription = issueDescription
        self.bookedSlot = bookedSlot
        self.statusID = statusID
        
    def createAppointment(self, bicycleName):
        self.bicycle = bicycleName
        return True
