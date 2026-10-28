# Parcel shipping cost by weight band and distance.
weight = float(input("Parcel weight (kg): "))
distance = int(input("Distance (km): "))

if weight <= 0 or distance <= 0:
    print("Invalid parcel")
else:
    if weight <= 2:
        cost = 40
    elif weight <= 10:
        cost = 80
    else:
        cost = 150

    if distance > 500:
        cost += 60
    elif distance > 100:
        cost += 25

    print("Cost:", cost)
