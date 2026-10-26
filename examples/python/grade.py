# Grade classifier: an elif chain plus an `or` range check.
score = int(input("Score: "))

if score < 0 or score > 100:
    print("Invalid score")
elif score >= 90:
    print("Grade A")
elif score >= 75:
    print("Grade B")
elif score >= 40:
    print("Grade C")
else:
    print("Fail")
