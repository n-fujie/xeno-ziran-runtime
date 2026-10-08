// Embedded CPython running the simulator engine (backend/xzr) in-process.
//
// The interpreter is configured isolated (no environment variables, no user site, no bytecode writes into the
// signed bundle); its home is <bundle>/python (standard library), the engine lives in <bundle>/app and numpy in
// <bundle>/app_packages. Only two engine functions are reachable from the app: xzr.native.bridge.handle (one
// allowlisted API request) and xzr.native.bridge.poll (pending stream items). Nothing evaluates source text.

#ifndef XZRPython_h
#define XZRPython_h

#include <stdbool.h>

/// Start the interpreter and import the bridge. Returns NULL on success, or a malloc'd error message (caller frees).
char *xzr_python_start(const char *resource_path);

/// True once xzr_python_start succeeded.
bool xzr_python_ready(void);

/// One bridge request (JSON) → response (JSON). Returns a malloc'd UTF-8 string (caller frees); on an interpreter
/// failure the response is a JSON error with status 500. Thread-safe (takes the GIL).
char *xzr_python_handle(const char *request_json);

/// Pending stream items (JSON array). Same ownership and threading as xzr_python_handle.
char *xzr_python_poll(void);

#if DEBUG
/// Debug builds only (tests): run the behavioural conformance snapshot against a reference (JSON) — see
/// xzr.native.conformance.run_json. Not present in Release builds.
char *xzr_python_conformance(const char *reference_json);
/// Debug builds only (tests): xzr.native.conformance.benchmark_json(scenario) — timings on this device.
char *xzr_python_benchmark(const char *scenario);
#endif

#endif
