/* C twin for vector_growth.logos. */

#include <stdint.h>
#include <stdio.h>

int main(void) {
    enum { N = 65 };
    int64_t values[N];
    int64_t total = 0;

    for (int64_t i = 0; i < N; i++) {
        values[i] = i * 3 + 1;
        total += values[i];
    }
    printf("%lld\n", (long long)N);
    printf("%lld\n", (long long)values[0]);
    printf("%lld\n", (long long)values[N - 1]);
    printf("%lld\n", (long long)total);
    return 0;
}
