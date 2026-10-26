# Nested conditions: the inner if is reached only when attempts < 3.
# With a small test budget, the Coverage tab shows suggestions, and
# marks those that cannot reach the inner branch on their own.
attempts = int(input("Failed attempts: "))
age = int(input("Account age (days): "))

if attempts < 3:
    if age >= 30:
        print("Login allowed")
    else:
        print("New account: verify email")
else:
    print("Locked")
