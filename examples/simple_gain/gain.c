/* gain.c - Simple gain model: y = K * x */
#include "gain.h"

double gain(double x, double K) {
    return K * x;
}
