/* C twin for shifts_signed.logos. All signed shifts are positive and in range. */

#include <stdint.h>
#include <stdio.h>

int main(void) {
    int64_t one = 1;
    int64_t wide = one << 40;
    /* Read from an array so the two shifts below cannot be folded away:
       they are the case's test of shl and shr by a runtime amount. */
    int64_t operands[4] = {7, 5, 768, 3};

    printf("%lld\n", (long long)wide);
    printf("%lld\n", (long long)(wide >> 8));
    printf("%lld\n", (long long)(operands[0] << operands[1]));
    printf("%lld\n", (long long)(operands[2] >> operands[3]));
    return 0;
}
