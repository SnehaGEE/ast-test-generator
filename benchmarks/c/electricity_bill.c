/* Electricity bill with slab rates and a surcharge on large bills. */
#include <stdio.h>

int main(void) {
    int units;
    float bill;

    printf("Enter units consumed: ");
    scanf("%d", &units);

    if (units < 0) {
        printf("Invalid reading\n");
        return 1;
    }

    if (units <= 100) {
        bill = units * 1.5f;
    } else if (units <= 200) {
        bill = 150 + (units - 100) * 2.5f;
    } else if (units <= 300) {
        bill = 400 + (units - 200) * 4.0f;
    } else {
        bill = 800 + (units - 300) * 6.0f;
    }

    if (bill > 1000) {
        bill = bill * 1.05f;
        printf("Surcharge applied\n");
    }

    printf("Bill: %.2f\n", bill);
    return 0;
}
