/* Standard header file for FMI 2.0 type definitions */
/* From https://github.com/modelica/fmi-standard */

#ifndef fmi2TypesPlatform_h
#define fmi2TypesPlatform_h

/* Platform and samples specific definitions */

/* Type definitions of variables passed as function arguments */
#define fmi2TypesPlatform "default"

typedef void*           fmi2Component;
typedef void*           fmi2ComponentEnvironment;
typedef void*           fmi2FMUstate;
typedef unsigned int    fmi2ValueReference;
typedef double          fmi2Real;
typedef int             fmi2Integer;
typedef int             fmi2Boolean;
typedef char            fmi2Char;
typedef const fmi2Char* fmi2String;
typedef char            fmi2Byte;

/* Values for fmi2Boolean */
#define fmi2True  1
#define fmi2False 0

#endif /* fmi2TypesPlatform_h */
