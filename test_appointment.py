from models.appointment import Appointment

appointment1 = Appointment(
    id=1,
    bicycle="Mountain Bike",
    issueDescription="Brake adjustment",
    bookedSlot="2026-10-20 10:00",
    statusID=1
)

print("Appointment ID:", appointment1.id)
print("Bicycle:", appointment1.bicycle)
print("Repair:", appointment1.issueDescription)
print("Date and Time:", appointment1.bookedSlot)
print("Status ID:", appointment1.statusID)
