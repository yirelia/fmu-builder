/* fmi2_adapter.h - Interface between fixed FMI wrapper and generated adapter
 * Generated adapters must implement these functions.
 * C89 compatible.
 */

#ifndef FMI2_ADAPTER_H
#define FMI2_ADAPTER_H

#include "fmi2/fmi2TypesPlatform.h"

/* Model metadata - defined in adapter.c */
extern const char* MODEL_GUID;
extern const char* MODEL_NAME;
extern const int NUM_INPUTS;
extern const int NUM_OUTPUTS;
extern const int NUM_PARAMS;
extern double PARAM_DEFAULTS[];

/* Adapter functions - implemented in adapter.c */

/* Initialize model state. Called once per instance.
 * params: array of parameter values (length = NUM_PARAMS)
 * Returns: user state pointer (NULL if stateless) */
void* model_initialize(const double* params);

/* Execute one simulation step.
 * dt:      communication step size in seconds
 * inputs:  array of input values (length = NUM_INPUTS)
 * outputs: array to fill with output values (length = NUM_OUTPUTS)
 * params:  array of parameter values (length = NUM_PARAMS)
 * state:   user state pointer from model_initialize */
void model_step(double dt, const double* inputs, double* outputs,
                const double* params, void* state);

/* Cleanup model state. Called once per instance.
 * state: user state pointer from model_initialize */
void model_terminate(void* state);

#endif /* FMI2_ADAPTER_H */
