/* Standard header file for FMI 2.0 function type definitions */
/* From https://github.com/modelica/fmi-standard */

#ifndef fmi2FunctionTypes_h
#define fmi2FunctionTypes_h

#include "fmi2TypesPlatform.h"

/* Type definitions */
typedef enum {
    fmi2OK,
    fmi2Warning,
    fmi2Discard,
    fmi2Error,
    fmi2Fatal,
    fmi2Pending
} fmi2Status;

typedef enum {
    fmi2ModelExchange,
    fmi2CoSimulation
} fmi2Type;

typedef enum {
    fmi2DoStepStatus,
    fmi2PendingStatus,
    fmi2LastSuccessfulTime,
    fmi2Terminated
} fmi2StatusKind;

/* Callback function types */
typedef void  (*fmi2CallbackLogger)        (fmi2ComponentEnvironment, fmi2String, fmi2Status, fmi2String, fmi2String, ...);
typedef void* (*fmi2CallbackAllocateMemory)(size_t, size_t);
typedef void  (*fmi2CallbackFreeMemory)    (void*);
typedef void  (*fmi2StepFinished)          (fmi2ComponentEnvironment, fmi2Status);

typedef struct {
    fmi2CallbackLogger         logger;
    fmi2CallbackAllocateMemory allocateMemory;
    fmi2CallbackFreeMemory     freeMemory;
    fmi2StepFinished           stepFinished;
    fmi2ComponentEnvironment   componentEnvironment;
} fmi2CallbackFunctions;

/* Function pointer types for all FMI2 functions */
/* Common functions */
typedef const char*    (*fmi2GetTypesPlatformTYPE)(void);
typedef const char*    (*fmi2GetVersionTYPE)(void);
typedef fmi2Status     (*fmi2SetDebugLoggingTYPE)(fmi2Component, fmi2Boolean, size_t, const fmi2String[]);
typedef fmi2Component  (*fmi2InstantiateTYPE)(fmi2String, fmi2Type, fmi2String, fmi2String, const fmi2CallbackFunctions*, fmi2Boolean, fmi2Boolean);
typedef void           (*fmi2FreeInstanceTYPE)(fmi2Component);
typedef fmi2Status     (*fmi2SetupExperimentTYPE)(fmi2Component, fmi2Boolean, fmi2Real, fmi2Real, fmi2Boolean, fmi2Real);
typedef fmi2Status     (*fmi2EnterInitializationModeTYPE)(fmi2Component);
typedef fmi2Status     (*fmi2ExitInitializationModeTYPE)(fmi2Component);
typedef fmi2Status     (*fmi2TerminateTYPE)(fmi2Component);
typedef fmi2Status     (*fmi2ResetTYPE)(fmi2Component);
typedef fmi2Status     (*fmi2GetRealTYPE)(fmi2Component, const fmi2ValueReference[], size_t, fmi2Real[]);
typedef fmi2Status     (*fmi2GetIntegerTYPE)(fmi2Component, const fmi2ValueReference[], size_t, fmi2Integer[]);
typedef fmi2Status     (*fmi2GetBooleanTYPE)(fmi2Component, const fmi2ValueReference[], size_t, fmi2Boolean[]);
typedef fmi2Status     (*fmi2GetStringTYPE)(fmi2Component, const fmi2ValueReference[], size_t, fmi2String[]);
typedef fmi2Status     (*fmi2SetRealTYPE)(fmi2Component, const fmi2ValueReference[], size_t, const fmi2Real[]);
typedef fmi2Status     (*fmi2SetIntegerTYPE)(fmi2Component, const fmi2ValueReference[], size_t, const fmi2Integer[]);
typedef fmi2Status     (*fmi2SetBooleanTYPE)(fmi2Component, const fmi2ValueReference[], size_t, const fmi2Boolean[]);
typedef fmi2Status     (*fmi2SetStringTYPE)(fmi2Component, const fmi2ValueReference[], size_t, const fmi2String[]);

/* Co-Simulation specific functions */
typedef fmi2Status     (*fmi2DoStepTYPE)(fmi2Component, fmi2Real, fmi2Real, fmi2Boolean);
typedef fmi2Status     (*fmi2CancelStepTYPE)(fmi2Component);
typedef fmi2Status     (*fmi2GetStatusTYPE)(fmi2Component, const fmi2StatusKind, fmi2Status*);
typedef fmi2Status     (*fmi2GetRealStatusTYPE)(fmi2Component, const fmi2StatusKind, fmi2Real*);
typedef fmi2Status     (*fmi2GetIntegerStatusTYPE)(fmi2Component, const fmi2StatusKind, fmi2Integer*);
typedef fmi2Status     (*fmi2GetBooleanStatusTYPE)(fmi2Component, const fmi2StatusKind, fmi2Boolean*);
typedef fmi2Status     (*fmi2GetStringStatusTYPE)(fmi2Component, const fmi2StatusKind, fmi2String*);
typedef fmi2Status     (*fmi2SetRealInputDerivativesTYPE)(fmi2Component, const fmi2ValueReference[], size_t, const fmi2Integer[], const fmi2Real[]);
typedef fmi2Status     (*fmi2GetRealOutputDerivativesTYPE)(fmi2Component, const fmi2ValueReference[], size_t, const fmi2Integer[], fmi2Real[]);

#endif /* fmi2FunctionTypes_h */
