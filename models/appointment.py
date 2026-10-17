# Feature 3 - Booking System 
# This class stores bicycle repair appointment information.

class Appointment:

    # Start a new appointment with the required information 
    def __init__(self, id, bicycle, issueDescription, bookedSlot, statusID):

        # Input appointment ID
        self.id = id

        # Input Bicycle Information
        self.bicycle = bicycle

        # Input Repair Issue 
        self.issueDescription = issueDescription

        # Input Appointment Date and Time 
        self.bookedSlot = bookedSlot

        # Input Appointment Status ID
        self.statusID = statusID

    # Update bicycle Information 
    def createAppointment(self, bicycleName):

        # Replace existing bicycle information
        self.bicycle = bicycleName

        #Indicate method has been completed 
        return True
