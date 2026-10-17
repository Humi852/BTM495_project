# Feature 3 - Booking System 
# Run Test for Appointment Class 

# Input Appointment class from appointment.py
from models.appointment import Appointment

# Create bicycle Repair Example 
appointment1 = Appointment(
    id=1,
    bicycle="Mountain Bike",
    issueDescription="Brake adjustment",
    bookedSlot="2026-10-20 10:00",
    statusID=1
)

# Display Appointment Information
print("Appointment ID:", appointment1.id)
print("Bicycle:", appointment1.bicycle)
print("Repair:", appointment1.issueDescription)
print("Date and Time:", appointment1.bookedSlot)
print("Status ID:", appointment1.statusID)

# Test Create Appointment() Method 
print("\nTesting createAppointment method:")

# Call Method to update bicycle Information
result = appointment1.createAppointment("Road Bike")

# Display Method Completed 
print("Method result:", result)

# Display Bicycle Information
print("Updated bicycle:", appointment1.bicycle)
