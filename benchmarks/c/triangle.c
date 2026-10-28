/* Classic triangle classification from three side lengths. */
#include <stdio.h>

int main(void) {
    int a, b, c;

    printf("Enter three sides: ");
    scanf("%d %d %d", &a, &b, &c);

    if (a <= 0 || b <= 0 || c <= 0) {
        printf("Invalid side\n");
        return 1;
    }

    if (a + b <= c || a + c <= b || b + c <= a) {
        printf("Not a triangle\n");
    } else if (a == b && b == c) {
        printf("Equilateral\n");
    } else if (a == b || b == c || a == c) {
        printf("Isosceles\n");
    } else {
        printf("Scalene\n");
    }
    return 0;
}
