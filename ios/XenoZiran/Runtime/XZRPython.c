#include "XZRPython.h"

#include <Python/Python.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static PyObject *bridge_handle = NULL;
static PyObject *bridge_poll = NULL;
static bool started = false;

static char *dup_string(const char *s) {
    size_t n = strlen(s);
    char *out = malloc(n + 1);
    if (out) memcpy(out, s, n + 1);
    return out;
}

static char *format_error(const char *what, const char *detail) {
    char buf[1024];
    snprintf(buf, sizeof buf, "%s%s%s", what, detail ? ": " : "", detail ? detail : "");
    return dup_string(buf);
}

// The pending Python exception as text (clears it).
static char *exception_text(void) {
    PyObject *exc = PyErr_GetRaisedException();
    if (!exc) return dup_string("unknown error");
    PyObject *s = PyObject_Str(exc);
    const char *msg = s ? PyUnicode_AsUTF8(s) : NULL;
    const char *type = Py_TYPE(exc)->tp_name;
    char buf[1024];
    snprintf(buf, sizeof buf, "%s: %s", type, msg ? msg : "?");
    Py_XDECREF(s);
    Py_DECREF(exc);
    PyErr_Clear();
    return dup_string(buf);
}

static PyObject *bundle_path(const char *resource_path, const char *sub) {
    char buf[4096];
    snprintf(buf, sizeof buf, "%s/%s", resource_path, sub);
    return PyUnicode_DecodeFSDefault(buf);
}

char *xzr_python_start(const char *resource_path) {
    if (started) return NULL;
    PyPreConfig preconfig;
    PyConfig config;
    PyStatus status;

    PyPreConfig_InitIsolatedConfig(&preconfig);
    preconfig.utf8_mode = 1;
    status = Py_PreInitialize(&preconfig);
    if (PyStatus_Exception(status)) return format_error("Python pre-initialisation failed", status.err_msg);

    PyConfig_InitIsolatedConfig(&config);
    config.use_system_logger = 1;   // Python output goes to the unified log
    config.buffered_stdio = 0;
    config.write_bytecode = 0;      // the bundle is signed and read-only
    config.install_signal_handlers = 0;
    config.site_import = 1;
#if DEBUG
    if (getenv("XZR_IMPORTTIME")) config.import_time = 1;  // diagnostics: per-module import times to the log
#endif

    char home[4096];
    snprintf(home, sizeof home, "%s/python", resource_path);
    wchar_t *whome = Py_DecodeLocale(home, NULL);
    status = PyConfig_SetString(&config, &config.home, whome);
    PyMem_RawFree(whome);
    if (PyStatus_Exception(status)) {
        PyConfig_Clear(&config);
        return format_error("Python home could not be set", status.err_msg);
    }
    status = Py_InitializeFromConfig(&config);
    PyConfig_Clear(&config);
    if (PyStatus_Exception(status)) return format_error("Python could not start", status.err_msg);

    // app_packages (numpy) as a site directory; the engine package in app/ first on sys.path
    PyObject *site = PyImport_ImportModule("site");
    PyObject *packages = bundle_path(resource_path, "app_packages");
    PyObject *r = (site && packages) ? PyObject_CallMethod(site, "addsitedir", "O", packages) : NULL;
    Py_XDECREF(packages);
    Py_XDECREF(site);
    if (!r) return format_error("app_packages could not be added", exception_text());
    Py_DECREF(r);

    PyObject *sys_path = PySys_GetObject("path");  // borrowed
    PyObject *app = bundle_path(resource_path, "app");
    if (!sys_path || !app || PyList_Insert(sys_path, 0, app) != 0) {
        Py_XDECREF(app);
        return format_error("the engine path could not be set", exception_text());
    }
    Py_DECREF(app);

    PyObject *bridge = PyImport_ImportModule("xzr.native.bridge");
    if (!bridge) return format_error("the simulator engine could not be loaded", exception_text());
    bridge_handle = PyObject_GetAttrString(bridge, "handle");
    bridge_poll = PyObject_GetAttrString(bridge, "poll");
    Py_DECREF(bridge);
    if (!bridge_handle || !bridge_poll) return format_error("the engine bridge is incomplete", exception_text());

    started = true;
    PyEval_SaveThread();  // release the GIL: requests and the engine's own threads take it as needed
    return NULL;
}

bool xzr_python_ready(void) { return started; }

static char *result_string(PyObject *result) {
    if (!result) {
        char *err = exception_text();
        PyObject *msg = PyUnicode_FromString(err);
        free(err);
        PyObject *json = PyImport_ImportModule("json");
        PyObject *body = msg ? Py_BuildValue("{s:i,s:s,s:{s:O}}", "status", 500, "kind", "json", "body", "detail", msg) : NULL;
        PyObject *text = (json && body) ? PyObject_CallMethod(json, "dumps", "O", body) : NULL;
        const char *u = text ? PyUnicode_AsUTF8(text) : NULL;
        char *out = dup_string(u ? u : "{\"status\":500,\"kind\":\"json\",\"body\":{\"detail\":\"runtime error\"}}");
        Py_XDECREF(text);
        Py_XDECREF(body);
        Py_XDECREF(json);
        Py_XDECREF(msg);
        PyErr_Clear();
        return out;
    }
    const char *u = PyUnicode_AsUTF8(result);
    char *out = dup_string(u ? u : "{\"status\":500,\"kind\":\"json\",\"body\":{\"detail\":\"invalid runtime reply\"}}");
    Py_DECREF(result);
    return out;
}

char *xzr_python_handle(const char *request_json) {
    if (!started) return dup_string("{\"status\":503,\"kind\":\"json\",\"body\":{\"detail\":\"the simulator runtime is not running\"}}");
    PyGILState_STATE g = PyGILState_Ensure();
    PyObject *arg = PyUnicode_FromString(request_json);
    PyObject *result = arg ? PyObject_CallOneArg(bridge_handle, arg) : NULL;
    Py_XDECREF(arg);
    char *out = result_string(result);
    PyGILState_Release(g);
    return out;
}

char *xzr_python_poll(void) {
    if (!started) return dup_string("[]");
    PyGILState_STATE g = PyGILState_Ensure();
    PyObject *result = PyObject_CallNoArgs(bridge_poll);
    char *out;
    if (!result) {
        char *err = exception_text();
        fprintf(stderr, "xzr poll failed: %s\n", err);
        free(err);
        out = dup_string("[]");
    } else {
        out = result_string(result);
    }
    PyGILState_Release(g);
    return out;
}

#if DEBUG
static char *call_conformance(const char *func, const char *arg) {
    if (!started) return dup_string("{\"error\":\"runtime not started\"}");
    PyGILState_STATE g = PyGILState_Ensure();
    PyObject *mod = PyImport_ImportModule("xzr.native.conformance");
    PyObject *result = mod ? PyObject_CallMethod(mod, func, "s", arg) : NULL;
    Py_XDECREF(mod);
    char *out;
    if (!result) {
        char *err = exception_text();
        for (char *c = err; *c; c++) if (*c == '"' || *c == '\\' || *c == '\n') *c = ' ';
        char buf[1200];
        snprintf(buf, sizeof buf, "{\"error\":\"%s\"}", err);
        free(err);
        out = dup_string(buf);
    } else {
        const char *u = PyUnicode_AsUTF8(result);
        out = dup_string(u ? u : "{}");
        Py_DECREF(result);
    }
    PyGILState_Release(g);
    return out;
}

char *xzr_python_conformance(const char *reference_json) { return call_conformance("run_json", reference_json); }
char *xzr_python_benchmark(const char *scenario) { return call_conformance("benchmark_json", scenario); }
#endif
