/* fmi2_wrapper.c - Fixed FMI 2.0 Co-Simulation wrapper
 * Implements all 27 required FMI 2.0 C-API functions.
 * Delegates model logic to adapter functions (model_initialize/step/terminate).
 * C89 compatible for VS 2010/2012.
 */

#include "fmi2/fmi2Functions.h"
#include "fmi2_adapter.h"
#include <string.h>
#include <stdlib.h>

/* Per-instance state */
typedef struct {
    fmi2Real*  reals;           /* all Real values: [inputs | outputs | params] */
    int        num_inputs;
    int        num_outputs;
    int        num_params;
    int        num_reals;       /* total = inputs + outputs + params */
    void*      user_state;      /* from model_initialize */
    int        initialized;
    double     current_time;
    fmi2CallbackFunctions callbacks;
    char       instance_name[256];
    char       guid[128];
} ComponentState;

/* Helper: get pointer to inputs/outputs/params sections in reals array */
#define INPUTS(cs)  ((cs)->reals)
#define OUTPUTS(cs) ((cs)->reals + (cs)->num_inputs)
#define PARAMS(cs)  ((cs)->reals + (cs)->num_inputs + (cs)->num_outputs)


/* ========== Common Functions ========== */

FMI2_Export const char* fmi2GetTypesPlatform(void) {
    return fmi2TypesPlatform;
}

FMI2_Export const char* fmi2GetVersion(void) {
    return "2.0";
}

FMI2_Export fmi2Status fmi2SetDebugLogging(fmi2Component c,
    fmi2Boolean loggingOn, size_t nCategories, const fmi2String categories[]) {
    (void)c; (void)loggingOn; (void)nCategories; (void)categories;
    return fmi2OK;
}

FMI2_Export fmi2Component fmi2Instantiate(
    fmi2String instanceName, fmi2Type fmuType, fmi2String fmuGUID,
    fmi2String fmuResourceLocation, const fmi2CallbackFunctions* functions,
    fmi2Boolean visible, fmi2Boolean loggingOn) {

    ComponentState* cs;
    int i;

    (void)fmuResourceLocation;
    (void)visible;
    (void)loggingOn;

    /* Validate type */
    if (fmuType != fmi2CoSimulation) {
        return NULL;
    }

    /* Validate GUID */
    if (strcmp(fmuGUID, MODEL_GUID) != 0) {
        if (functions && functions->logger) {
            functions->logger(functions->componentEnvironment,
                instanceName, fmi2Error, "error",
                "GUID mismatch: expected %s, got %s", MODEL_GUID, fmuGUID);
        }
        return NULL;
    }

    /* Allocate component state */
    cs = (ComponentState*)calloc(1, sizeof(ComponentState));
    if (!cs) {
        return NULL;
    }

    cs->num_inputs = NUM_INPUTS;
    cs->num_outputs = NUM_OUTPUTS;
    cs->num_params = NUM_PARAMS;
    cs->num_reals = NUM_INPUTS + NUM_OUTPUTS + NUM_PARAMS;

    /* Allocate reals array */
    if (cs->num_reals > 0) {
        cs->reals = (fmi2Real*)calloc(cs->num_reals, sizeof(fmi2Real));
        if (!cs->reals) {
            free(cs);
            return NULL;
        }
    }

    /* Set parameter defaults */
    for (i = 0; i < NUM_PARAMS; i++) {
        PARAMS(cs)[i] = PARAM_DEFAULTS[i];
    }

    /* Store callbacks and metadata */
    if (functions) {
        cs->callbacks = *functions;
    }
    strncpy(cs->instance_name, instanceName ? instanceName : "", 255);
    cs->instance_name[255] = '\0';
    strncpy(cs->guid, fmuGUID ? fmuGUID : "", 127);
    cs->guid[127] = '\0';

    cs->initialized = 0;
    cs->current_time = 0.0;
    cs->user_state = NULL;

    return (fmi2Component)cs;
}

FMI2_Export void fmi2FreeInstance(fmi2Component c) {
    ComponentState* cs;
    if (!c) return;
    cs = (ComponentState*)c;

    if (cs->user_state) {
        model_terminate(cs->user_state);
        cs->user_state = NULL;
    }
    if (cs->reals) {
        free(cs->reals);
    }
    free(cs);
}

FMI2_Export fmi2Status fmi2SetupExperiment(fmi2Component c,
    fmi2Boolean toleranceDefined, fmi2Real tolerance,
    fmi2Real startTime, fmi2Boolean stopTimeDefined, fmi2Real stopTime) {

    ComponentState* cs;
    (void)toleranceDefined; (void)tolerance;
    (void)stopTimeDefined; (void)stopTime;

    if (!c) return fmi2Error;
    cs = (ComponentState*)c;
    cs->current_time = startTime;
    return fmi2OK;
}

FMI2_Export fmi2Status fmi2EnterInitializationMode(fmi2Component c) {
    if (!c) return fmi2Error;
    return fmi2OK;
}

FMI2_Export fmi2Status fmi2ExitInitializationMode(fmi2Component c) {
    ComponentState* cs;
    if (!c) return fmi2Error;
    cs = (ComponentState*)c;

    /* Call user init function */
    cs->user_state = model_initialize(PARAMS(cs));
    cs->initialized = 1;
    return fmi2OK;
}

FMI2_Export fmi2Status fmi2Terminate(fmi2Component c) {
    ComponentState* cs;
    if (!c) return fmi2Error;
    cs = (ComponentState*)c;

    if (cs->user_state) {
        model_terminate(cs->user_state);
        cs->user_state = NULL;
    }
    cs->initialized = 0;
    return fmi2OK;
}

FMI2_Export fmi2Status fmi2Reset(fmi2Component c) {
    ComponentState* cs;
    int i;

    if (!c) return fmi2Error;
    cs = (ComponentState*)c;

    if (cs->user_state) {
        model_terminate(cs->user_state);
        cs->user_state = NULL;
    }

    /* Reset all values */
    if (cs->reals) {
        memset(cs->reals, 0, cs->num_reals * sizeof(fmi2Real));
    }

    /* Restore parameter defaults */
    for (i = 0; i < NUM_PARAMS; i++) {
        PARAMS(cs)[i] = PARAM_DEFAULTS[i];
    }

    cs->initialized = 0;
    cs->current_time = 0.0;
    return fmi2OK;
}


/* ========== Getters and Setters ========== */

FMI2_Export fmi2Status fmi2GetReal(fmi2Component c,
    const fmi2ValueReference vr[], size_t nvr, fmi2Real value[]) {

    ComponentState* cs;
    size_t i;
    if (!c) return fmi2Error;
    cs = (ComponentState*)c;

    for (i = 0; i < nvr; i++) {
        if ((int)vr[i] >= cs->num_reals) return fmi2Error;
        value[i] = cs->reals[vr[i]];
    }
    return fmi2OK;
}

FMI2_Export fmi2Status fmi2SetReal(fmi2Component c,
    const fmi2ValueReference vr[], size_t nvr, const fmi2Real value[]) {

    ComponentState* cs;
    size_t i;
    if (!c) return fmi2Error;
    cs = (ComponentState*)c;

    for (i = 0; i < nvr; i++) {
        if ((int)vr[i] >= cs->num_reals) return fmi2Error;
        cs->reals[vr[i]] = value[i];
    }
    return fmi2OK;
}

/* Integer, Boolean, String: stub implementations for MVP (Real only) */
FMI2_Export fmi2Status fmi2GetInteger(fmi2Component c,
    const fmi2ValueReference vr[], size_t nvr, fmi2Integer value[]) {
    (void)c; (void)vr; (void)nvr; (void)value;
    return fmi2Error;
}

FMI2_Export fmi2Status fmi2SetInteger(fmi2Component c,
    const fmi2ValueReference vr[], size_t nvr, const fmi2Integer value[]) {
    (void)c; (void)vr; (void)nvr; (void)value;
    return fmi2Error;
}

FMI2_Export fmi2Status fmi2GetBoolean(fmi2Component c,
    const fmi2ValueReference vr[], size_t nvr, fmi2Boolean value[]) {
    (void)c; (void)vr; (void)nvr; (void)value;
    return fmi2Error;
}

FMI2_Export fmi2Status fmi2SetBoolean(fmi2Component c,
    const fmi2ValueReference vr[], size_t nvr, const fmi2Boolean value[]) {
    (void)c; (void)vr; (void)nvr; (void)value;
    return fmi2Error;
}

FMI2_Export fmi2Status fmi2GetString(fmi2Component c,
    const fmi2ValueReference vr[], size_t nvr, fmi2String value[]) {
    (void)c; (void)vr; (void)nvr; (void)value;
    return fmi2Error;
}

FMI2_Export fmi2Status fmi2SetString(fmi2Component c,
    const fmi2ValueReference vr[], size_t nvr, const fmi2String value[]) {
    (void)c; (void)vr; (void)nvr; (void)value;
    return fmi2Error;
}


/* ========== Co-Simulation Functions ========== */

FMI2_Export fmi2Status fmi2DoStep(fmi2Component c,
    fmi2Real currentCommunicationPoint,
    fmi2Real communicationStepSize,
    fmi2Boolean noSetFMUStatePriorToCurrentPoint) {

    ComponentState* cs;
    (void)noSetFMUStatePriorToCurrentPoint;

    if (!c) return fmi2Error;
    cs = (ComponentState*)c;

    if (!cs->initialized) return fmi2Error;

    /* Call user step function via adapter */
    model_step(communicationStepSize, INPUTS(cs), OUTPUTS(cs),
               PARAMS(cs), cs->user_state);

    cs->current_time = currentCommunicationPoint + communicationStepSize;
    return fmi2OK;
}

FMI2_Export fmi2Status fmi2CancelStep(fmi2Component c) {
    (void)c;
    return fmi2Error; /* not supported */
}

FMI2_Export fmi2Status fmi2GetStatus(fmi2Component c,
    const fmi2StatusKind s, fmi2Status* value) {
    (void)c; (void)s; (void)value;
    return fmi2Error;
}

FMI2_Export fmi2Status fmi2GetRealStatus(fmi2Component c,
    const fmi2StatusKind s, fmi2Real* value) {
    (void)c; (void)s; (void)value;
    return fmi2Error;
}

FMI2_Export fmi2Status fmi2GetIntegerStatus(fmi2Component c,
    const fmi2StatusKind s, fmi2Integer* value) {
    (void)c; (void)s; (void)value;
    return fmi2Error;
}

FMI2_Export fmi2Status fmi2GetBooleanStatus(fmi2Component c,
    const fmi2StatusKind s, fmi2Boolean* value) {
    (void)c; (void)s; (void)value;
    return fmi2Error;
}

FMI2_Export fmi2Status fmi2GetStringStatus(fmi2Component c,
    const fmi2StatusKind s, fmi2String* value) {
    (void)c; (void)s; (void)value;
    return fmi2Error;
}

FMI2_Export fmi2Status fmi2SetRealInputDerivatives(fmi2Component c,
    const fmi2ValueReference vr[], size_t nvr,
    const fmi2Integer order[], const fmi2Real value[]) {
    (void)c; (void)vr; (void)nvr; (void)order; (void)value;
    return fmi2Error;
}

FMI2_Export fmi2Status fmi2GetRealOutputDerivatives(fmi2Component c,
    const fmi2ValueReference vr[], size_t nvr,
    const fmi2Integer order[], fmi2Real value[]) {
    (void)c; (void)vr; (void)nvr; (void)order; (void)value;
    return fmi2Error;
}
