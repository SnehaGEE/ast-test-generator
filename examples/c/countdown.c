/* Reads from standard input: echo 3 | ./countdown */
#include <stdio.h>

int main(void) {
    int n;
    scanf("%d", &n);

    while (n > 0) {
        printf("%d\n", n);
        n--;
    }

    printf("Lift-off\n");
    return 0;
}
