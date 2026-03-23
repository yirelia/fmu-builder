/* Standard header file for FMI 2.0 function declarations */
/* From https://github.com/modelica/fmi-standard */

#ifndef fmi2Functions_h
#define fmi2Functions_h

#include "fmi2TypesPlatform.h"
#include "fmi2FunctionTypes.h"
#include <stdlib.h>

/* Export macro */
#if !defined(FMI2_Export)
  #if defined _WIN32 || defined __CYGWIN__
    #define FMI2_Export __declspec(dllexport)
  #else
    #if __GNUC__ >= 4
      #define FMI2_Export __attribute__ ((visibility ("default")))
    #else
      #define FMI2_Export
    #endif
  #endif
#endif

/* Macro to construct function name (with optional prefix) */
#if !defined(FMI2_FUNCTION_PREFIX)
  #define FMI2_FUNCTION_PREFIX
#endif

/* Expanding macros for function names */
#define fmi2Paste(a,b)     a ## b
#define fmi2PasteB(a,b)    fmi2Paste(a,b)
#define fmi2FullName(name) fmi2PasteB(FMI2_FUNCTION_PREFIX, name)

/* Common functions */
#define fmi2GetTypesPlatform         fmi2FullName(fmi2GetTypesPlatform)
#define fmi2GetVersion               fmi2FullName(fmi2GetVersion)
#define fmi2SetDebugLogging          fmi2FullName(fmi2SetDebugLogging)
#define fmi2Instantiate              fmi2FullName(fmi2Instantiate)
#define fmi2FreeInstance             fmi2FullName(fmi2FreeInstance)
#define fmi2SetupExperiment          fmi2FullName(fmi2SetupExperiment)
#define fmi2EnterInitializationMode  fmi2FullName(fmi2EnterInitializationMode)
#define fmi2ExitInitializationMode   fmi2FullName(fmi2ExitInitializationMode)
#define fmi2Terminate                fmi2FullName(fmi2Terminate)
#define fmi2Reset                    fmi2FullName(fmi2Reset)
#define fmi2GetReal                  fmi2FullName(fmi2GetReal)
#define fmi2GetInteger               fmi2FullName(fmi2GetInteger)
#define fmi2GetBoolean               fmi2FullName(fmi2GetBoolean)
#define fmi2GetString                fmi2FullName(fmi2GetString)
#define fmi2SetReal                  fmi2FullName(fmi2SetReal)
#define fmi2SetInteger               fmi2FullName(fmi2SetInteger)
#define fmi2SetBoolean               fmi2FullName(fmi2SetBoolean)
#define fmi2SetString                fmi2FullName(fmi2SetString)

/* Co-Simulation functions */
#define fmi2DoStep                       fmi2FullName(fmi2DoStep)
#define fmi2CancelStep                   fmi2FullName(fmi2CancelStep)
#define fmi2GetStatus                    fmi2FullName(fmi2GetStatus)
#define fmi2GetRealStatus                fmi2FullName(fmi2GetRealStatus)
#define fmi2GetIntegerStatus             fmi2FullName(fmi2GetIntegerStatus)
#define fmi2GetBooleanStatus             fmi2FullName(fmi2GetBooleanStatus)
#define fmi2GetStringStatus              fmi2FullName(fmi2GetStringStatus)
#define fmi2SetRealInputDerivatives      fmi2FullName(fmi2SetRealInputDerivatives)
#define fmi2GetRealOutputDerivatives     fmi2FullName(fmi2GetRealOutputDerivatives)

/* Function declarations */
FMI2_Export const char* fmi2GetTypesPlatform(void);
FMI2_Export const char* fmi2GetVersion(void);
FMI2_Export fmi2Status  fmi2SetDebugLogging(fmi2Component, fmi2Boolean, size_t, const fmi2String[]);
FMI2_Export fmi2Component fmi2Instantiate(fmi2String, fmi2Type, fmi2String, fmi2String, const fmi2CallbackFunctions*, fmi2Boolean, fmi2Boolean);
FMI2_Export void        fmi2FreeInstance(fmi2Component);
FMI2_Export fmi2Status  fmi2SetupExperiment(fmi2Component, fmi2Boolean, fmi2Real, fmi2Real, fmi2Boolean, fmi2Real);
FMI2_Export fmi2Status  fmi2EnterInitializationMode(fmi2Component);
FMI2_Export fmi2Status  fmi2ExitInitializationMode(fmi2Component);
FMI2_Export fmi2Status  fmi2Terminate(fmi2Component);
FMI2_Export fmi2Status  fmi2Reset(fmi2Component);
FMI2_Export fmi2Status  fmi2GetReal(fmi2Component, const fmi2ValueReference[], size_t, fmi2Real[]);
FMI2_Export fmi2Status  fmi2GetInteger(fmi2Component, const fmi2ValueReference[], size_t, fmi2Integer[]);
FMI2_Export fmi2Status  fmi2GetBoolean(fmi2Component, const fmi2ValueReference[], size_t, fmi2Boolean[]);
FMI2_Export fmi2Status  fmi2GetString(fmi2Component, const fmi2ValueReference[], size_t, fmi2String[]);
FMI2_Export fmi2Status  fmi2SetReal(fmi2Component, const fmi2ValueReference[], size_t, const fmi2Real[]);
FMI2_Export fmi2Status  fmi2SetInteger(fmi2Component, const fmi2ValueReference[], size_t, const fmi2Integer[]);
FMI2_Export fmi2Status  fmi2SetBoolean(fmi2Component, const fmi2ValueReference[], size_t, const fmi2Boolean[]);
FMI2_Export fmi2Status  fmi2SetString(fmi2Component, const fmi2ValueReference[], size_t, const fmi2String[]);

/* Co-Simulation specific */
FMI2_Export fmi2Status fmi2DoStep(fmi2Component, fmi2Real, fmi2Real, fmi2Boolean);
FMI2_Export fmi2Status fmi2CancelStep(fmi2Component);
FMI2_Export fmi2Status fmi2GetStatus(fmi2Component, const fmi2StatusKind, fmi2Status*);
FMI2_Export fmi2Status fmi2GetRealStatus(fmi2Component, const fmi2StatusKind, fmi2Real*);
FMI2_Export fmi2Status fmi2GetIntegerStatus(fmi2Component, const fmi2StatusKind, fmi2Integer*);
FMI2_Export fmi2Status fmi2GetBooleanStatus(fmi2Component, const fmi2StatusKind, fmi2Boolean*);
FMI2_Export fmi2Status fmi2GetStringStatus(fmi2Component, const fmi2StatusKind, fmi2String*);
FMI2_Export fmi2Status fmi2SetRealInputDerivatives(fmi2Component, const fmi2ValueReference[], size_t, const fmi2Integer[], const fmi2Real[]);
FMI2_Export fmi2Status fmi2GetRealOutputDerivatives(fmi2Component, const fmi2ValueReference[], size_t, const fmi2Integer[], fmi2Real[]);

#endif /* fmi2Functions_h */
