#!/bin/sh
# Xcode build phase (after Copy Bundle Resources, before embedding/signing): install the on-device simulator runtime.
#
#   <bundle>/python/lib/python3.14   CPython standard library (from Python.xcframework), pruned of modules the app
#                                    never uses — notably every networking module (socket, ssl, http, urllib.request
#                                    remain unusable without _socket/_ssl) and the test suites
#   <bundle>/app/xzr, app/scenarios  the simulator engine (backend/xzr) and its bundled scenarios
#   <bundle>/app_packages/numpy      numpy for iOS (BeeWare wheel matching the build platform)
#   <bundle>/web                     the bundled interface (frontend, `npm run build:native`)
#
# Binary extension modules are converted into signed frameworks by BeeWare's utils.sh (App Store requirement).
set -e

XCF="vendor/py/Python.xcframework"
# an unsigned verification build (CODE_SIGNING_ALLOWED=NO) has no identity: sign the extension frameworks ad hoc
[ -n "$EXPANDED_CODE_SIGN_IDENTITY" ] || EXPANDED_CODE_SIGN_IDENTITY="-"
. "$PROJECT_DIR/$XCF/build/utils.sh"

WEB="$PROJECT_DIR/build/web"
if [ ! -f "$WEB/index.html" ]; then
    echo "error: the bundled interface is missing ($WEB). Build it first: (cd ../frontend && npm run build:native)"
    exit 1
fi

# 1. standard library
install_stdlib "$XCF"
PY_LIB="$CODESIGNING_FOLDER_PATH/python/lib/python3.14"
for d in test idlelib tkinter turtledemo ensurepip venv pydoc_data _pyrepl sqlite3 dbm curses http xmlrpc wsgiref \
         email/test lib2to3 site-packages; do
    rm -rf "$PY_LIB/$d"
done
for f in socket.py ssl.py socketserver.py smtplib.py ftplib.py imaplib.py poplib.py webbrowser.py antigravity.py \
         turtle.py pydoc.py; do
    rm -f "$PY_LIB/$f"
done
for m in _socket _ssl _hashlib _ctypes _ctypes_test _sqlite3 _dbm _remote_debugging _xxtestfuzz xxlimited \
         xxlimited_35 xxsubtype _testbuffer _testcapi _testclinic _testclinic_limited _testimportmultiple \
         _testinternalcapi _testlimitedcapi _testmultiphase _testsinglephase _interpchannels _interpqueues \
         _interpreters; do
    rm -f "$PY_LIB/lib-dynload/$m".cpython-*.so
done

# 2. engine + scenarios (exact source; FastAPI service and desktop experiment harnesses excluded)
mkdir -p "$CODESIGNING_FOLDER_PATH/app"
/usr/bin/python3 "$PROJECT_DIR/scripts/stage_engine.py" "$PROJECT_DIR/../backend" "$CODESIGNING_FOLDER_PATH/app"

# 3. numpy (iOS wheel for this platform)
if [ "$EFFECTIVE_PLATFORM_NAME" = "-iphonesimulator" ]; then
    WHEEL="$PROJECT_DIR/vendor/numpy-2.5.2.post1-cp314-cp314-ios_17_0_arm64_iphonesimulator.whl"
else
    WHEEL="$PROJECT_DIR/vendor/numpy-2.5.2.post1-cp314-cp314-ios_17_0_arm64_iphoneos.whl"
fi
PKG="$CODESIGNING_FOLDER_PATH/app_packages"
rm -rf "$PKG"
mkdir -p "$PKG"
/usr/bin/ditto -x -k "$WHEEL" "$PKG"
rm -rf "$PKG"/numpy/*/tests "$PKG"/numpy/tests "$PKG"/numpy/f2py "$PKG"/numpy/testing/_private/extbuild.py
rm -f "$PKG"/numpy/_core/_*_tests.cpython-*.so "$PKG"/numpy/_core/_simd.cpython-*.so
# static libraries and headers are for compiling against numpy, never used at run time; App Store validation
# rejects any standalone library outside a framework
find "$PKG" "$CODESIGNING_FOLDER_PATH/python" -name "*.a" -delete

# 4. interface
rm -rf "$CODESIGNING_FOLDER_PATH/web"
/usr/bin/ditto "$WEB" "$CODESIGNING_FOLDER_PATH/web"

# 5. bytecode, compiled now: the signed bundle is read-only, so without it every launch would recompile the
#    standard library, numpy and the engine from source (measured: ~7 s of a ~9 s start-up). Compiled by a host
#    CPython of the same minor version (identical bytecode format); unchecked-hash pycs do not depend on mtimes.
PYC_PY="${XZR_HOST_PYTHON314:-$(command -v python3.14 || echo /opt/homebrew/bin/python3.14)}"
if ! "$PYC_PY" -c 'import sys; sys.exit(sys.version_info[:2] != (3, 14))' 2>/dev/null; then
    echo "error: a host CPython 3.14 is needed to precompile the app's Python bytecode (brew install python@3.14,"
    echo "error: or set XZR_HOST_PYTHON314)"
    exit 1
fi
"$PYC_PY" -m compileall -q -j 0 --invalidation-mode unchecked-hash \
    "$PY_LIB" "$CODESIGNING_FOLDER_PATH/app" "$PKG" > /dev/null

# 6. extension modules → signed frameworks
process_dylibs "$XCF" python/lib/python3.14/lib-dynload
process_dylibs "$XCF" app_packages

# 7. the generated frameworks inherit MinimumOSVersion 13.0 and package type APPL from BeeWare's template, but numpy's binaries require
#    iOS 17: declare the app's deployment target (App Store validation rejects a plist minimum below the binary's)
#    and re-sign each one
for fw in "$CODESIGNING_FOLDER_PATH"/Frameworks/*.framework; do
    [ -f "$fw/$(basename "$fw" .framework).origin" ] || continue  # only frameworks made by process_dylibs
    plutil -replace MinimumOSVersion -string "$IPHONEOS_DEPLOYMENT_TARGET" "$fw/Info.plist"
    # BeeWare's template declares these as applications (APPL); they are frameworks, and App Store validation
    # otherwise takes them for apps ("Cannot determine the Apple ID from Bundle ID …numpy.random.-pcg64")
    plutil -replace CFBundlePackageType -string FMWK "$fw/Info.plist"
    /usr/bin/codesign --force --sign "$EXPANDED_CODE_SIGN_IDENTITY" ${OTHER_CODE_SIGN_FLAGS:-} -o runtime \
        --timestamp=none --preserve-metadata=identifier,entitlements,flags --generate-entitlement-der "$fw" 2>/dev/null
done
