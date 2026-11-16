/* C twin for float_arithmetic.logos. */

#include <stdio.h>

int main(void) {
    float a = 1.5f;
    float b = 2.25f;
    /* The operands come from an array so the compiler cannot fold the
       division and the subtraction away: these two lines are the case's
       test of fdiv and fsub, not of constant folding. */
    double parts[3] = {7.5, 2.5, 1.25};

    printf("%g\n", (double)(a + b));
    printf("%g\n", (double)(a * b));
    printf("%g\n", parts[0] / parts[1]);
    printf("%g\n", parts[0] - parts[2]);
    return 0;
}
