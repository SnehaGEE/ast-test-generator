/* Run with: ./grade 85 */
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char *argv[]) {
    int score = argc > 1 ? atoi(argv[1]) : 0;

    if (score < 0 || score > 100) {
        printf("Invalid score\n");
    } else if (score >= 90) {
        printf("Grade A\n");
    } else if (score >= 75) {
        printf("Grade B\n");
    } else if (score >= 40) {
        printf("Grade C\n");
    } else {
        printf("Fail\n");
    }

    return 0;
}
