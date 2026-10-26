# Thermostat: boundaries around negative constants.
temp = int(input("Temperature: "))

if temp < -10:
    print("Freezing")
elif temp <= 25:
    print("Comfortable")
else:
    print("Hot")
